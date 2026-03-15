"""
AIS Stream client — aisstream.io WebSocket.
World bbox subscription. Tanker/cargo filter applied at UI level.
All vessels admitted, zone-tagged. Map/table filter to tanker types.
"""

import asyncio
import json
import math
import threading
import time
from datetime import datetime, timezone

import websockets
from websockets.exceptions import InvalidStatus, ConnectionClosed

# ── Zone definitions ───────────────────────────────────────────────────────────
ZONES = {
    "Hormuz":       (22.0, 54.5, 27.5, 61.0),
    "Persian Gulf": (23.5, 47.5, 30.5, 56.5),
    "Gulf of Oman": (20.5, 55.5, 26.0, 62.5),
    "Gulf of Aden": (10.5, 42.5, 16.0, 51.5),
    "Red Sea":      (12.5, 38.0, 22.5, 44.5),
}

# World bbox — confirmed working on aisstream.io free tier
BOUNDING_BOXES = [[[-90, -180], [90, 180]]]

TANKER_TYPES = set(range(70, 90)) | {0}

# ── Module-level shared state ──────────────────────────────────────────────────
_vessels:           dict             = {}
_vessel_history:    dict             = {}
_type_registry:     dict             = {}
_debug_log:         list             = []
_stop_event:        threading.Event  = threading.Event()
_thread:            threading.Thread | None = None
_msg_count:         int              = 0
_raw_msg_count:     int              = 0
_last_msg_time:     datetime | None  = None
_stream_start_time: datetime | None  = None

NAV_STATUS = {
    0:"Underway", 1:"Anchored", 2:"No Command", 3:"Restricted",
    4:"By Draught", 5:"Moored", 6:"Aground", 7:"Fishing", 8:"Sailing", 15:"Unknown",
}


def _log(msg: str):
    global _debug_log
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    _debug_log.insert(0, f"[{ts}] {msg}")
    _debug_log = _debug_log[:100]
    print(f"[AIS] {msg}", flush=True)


def _classify_zone(lat: float, lon: float) -> str:
    for zone, (sw_lat, sw_lon, ne_lat, ne_lon) in ZONES.items():
        if sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon:
            return zone
    return "Other"


# ── Public API ─────────────────────────────────────────────────────────────────
def is_running() -> bool:
    return _thread is not None and _thread.is_alive()

def get_vessels() -> dict:
    return _vessels.copy()

def get_vessel_history() -> dict:
    return _vessel_history.copy()

def get_debug_log() -> list:
    return list(_debug_log)

def get_msg_count() -> int:
    return _msg_count

def get_raw_msg_count() -> int:
    return _raw_msg_count

def get_singapore_count() -> int:
    return 0  # compat shim

def get_last_msg_time() -> datetime | None:
    return _last_msg_time

def get_stream_start_time() -> datetime | None:
    return _stream_start_time

def get_coverage_status() -> dict:
    if not is_running():
        return {"status": "offline", "label": "Stream offline", "color": "gray"}
    elapsed = int((datetime.now(timezone.utc) - _stream_start_time).total_seconds()) if _stream_start_time else 0
    if _msg_count > 0:
        return {"status": "live",    "label": f"🟢 Live — {len(_vessels):,} vessels tracked", "color": "#26c06e"}
    elif elapsed > 60:
        return {"status": "dark",    "label": f"⚫ Connected — no transmissions yet ({elapsed}s)", "color": "#ef5350"}
    else:
        return {"status": "waiting", "label": f"⏳ Connecting… ({elapsed}s)", "color": "#ffd54f"}


def start_stream(api_key: str, demo_mode: bool = False):
    global _thread, _stop_event, _vessels, _vessel_history, _type_registry
    global _msg_count, _raw_msg_count, _stream_start_time

    stop_stream()
    _stop_event        = threading.Event()
    _vessels.clear()
    _vessel_history.clear()
    _type_registry.clear()
    _msg_count         = 0
    _raw_msg_count     = 0
    _stream_start_time = datetime.now(timezone.utc)

    target  = _demo_loop if (demo_mode or api_key == "DEMO") else _real_loop
    _thread = threading.Thread(
        target=target, args=(api_key, _stop_event),
        daemon=True, name="ais-stream",
    )
    _thread.start()
    mode = "DEMO" if (demo_mode or api_key == "DEMO") else "LIVE"
    _log(f"Stream started ({mode}) — world bbox")


def stop_stream():
    global _thread, _stop_event
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=3)
    _thread = None
    _log("Stream stopped")


# ── Real WebSocket ─────────────────────────────────────────────────────────────

def _real_loop(api_key: str, stop: threading.Event):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_ws_connect(api_key, stop))
    except Exception as e:
        _log(f"FATAL thread error: {type(e).__name__}: {e}")
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _ws_connect(api_key: str, stop: threading.Event):
    global _msg_count, _raw_msg_count, _last_msg_time

    url          = "wss://stream.aisstream.io/v0/stream"
    subscription = {"APIKey": api_key, "BoundingBoxes": BOUNDING_BOXES}
    retry_delay  = 3

    while not stop.is_set():
        try:
            _log(f"Connecting to {url}...")
            async with websockets.connect(
                url,
                open_timeout=15,
                ping_interval=None,   # disable — server pings timeout under high msg rate
                max_size=2**23,        # 8MB max message size
            ) as ws:
                _log("Connected — sending subscription...")
                await ws.send(json.dumps(subscription))
                _log(f"Subscribed: {json.dumps(BOUNDING_BOXES)}")
                retry_delay   = 3
                raw_count     = 0
                connect_time  = __import__('time').time()

                async for raw in ws:
                    if stop.is_set():
                        break
                    raw_count      += 1
                    _raw_msg_count += 1
                    # Yield to event loop periodically so connection stays healthy
                    if raw_count % 50 == 0:
                        await asyncio.sleep(0)
                    try:
                        data     = json.loads(raw)
                        msg_type = data.get("MessageType", "?")
                        meta     = data.get("MetaData", {})
                        if raw_count <= 5:
                            _log(f"MSG[{raw_count}] {msg_type} | {meta.get('ShipName','?')} | "
                                 f"lat={meta.get('latitude','?')} lon={meta.get('longitude','?')}")
                        vessel = _parse_message(data)
                        if vessel:
                            _upsert_vessel(vessel)
                            _msg_count    += 1
                            _last_msg_time = datetime.now(timezone.utc)
                            if _msg_count == 1:
                                _log(f"First vessel: {vessel['name']} zone={vessel['zone']}")
                            elif _msg_count % 200 == 0:
                                _log(f"{_msg_count:,} msgs | {len(_vessels):,} vessels")
                    except Exception as e:
                        _log(f"Parse error msg {raw_count}: {type(e).__name__}: {e}")

        except InvalidStatus as e:
            _log(f"Auth error: {e} — stopping")
            stop.set()
            return
        except ConnectionClosed as e:
            if stop.is_set(): break
            jitter = __import__('random').uniform(0, retry_delay * 0.3)
            wait   = retry_delay + jitter
            _log(f"Connection closed: {e} — retry in {wait:.0f}s")
            time.sleep(wait)
            retry_delay = min(retry_delay * 2, 120)
        except OSError as e:
            # ConnectionRefusedError / temporary IP block — wait longer
            if stop.is_set(): break
            jitter = __import__('random').uniform(0, retry_delay * 0.3)
            wait   = retry_delay + jitter
            _log(f"Connection refused (temp block?): {e} — retry in {wait:.0f}s")
            time.sleep(wait)
            retry_delay = min(retry_delay * 2, 120)
        except Exception as e:
            if stop.is_set(): break
            jitter = __import__('random').uniform(0, retry_delay * 0.3)
            wait   = retry_delay + jitter
            _log(f"WS error: {type(e).__name__}: {e} — retry in {wait:.0f}s")
            time.sleep(wait)
            retry_delay = min(retry_delay * 2, 120)


# ── Message parsing ────────────────────────────────────────────────────────────

def _parse_message(data: dict) -> dict | None:
    msg_type = data.get("MessageType", "")
    meta     = data.get("MetaData", {})
    msg      = data.get("Message", {})

    mmsi = str(meta.get("MMSI", "")).strip()
    if not mmsi or mmsi == "0":
        return None

    lat = meta.get("latitude", meta.get("Latitude"))
    lon = meta.get("longitude", meta.get("Longitude"))
    if lat is None or lon is None:
        return None
    lat, lon = float(lat), float(lon)
    if lat == 0.0 and lon == 0.0:
        return None

    name = str(meta.get("ShipName", meta.get("ship_name", f"MMSI-{mmsi}"))).strip() or f"MMSI-{mmsi}"
    zone = _classify_zone(lat, lon)
    ts   = datetime.now(timezone.utc).isoformat()

    sog = 0.0; cog = 0.0; heading = 511; nav_status = 15; ship_type = 0
    destination = ""; imo = ""; callsign = ""

    if msg_type == "PositionReport":
        pr         = msg.get("PositionReport", {})
        sog        = float(pr.get("Sog", 0.0))
        cog        = float(pr.get("Cog", 0.0))
        heading    = int(pr.get("TrueHeading", 511))
        nav_status = int(pr.get("NavigationalStatus", 15))
    elif msg_type == "ShipStaticData":
        sd          = msg.get("ShipStaticData", {})
        ship_type   = int(sd.get("Type", 0))
        name        = str(sd.get("Name", name)).strip() or name
        imo         = str(sd.get("ImoNumber", ""))
        callsign    = str(sd.get("CallSign", ""))
        destination = str(sd.get("Destination", ""))
        nav_status  = 5
    elif msg_type == "ExtendedClassBPositionReport":
        pr         = msg.get("ExtendedClassBPositionReport", {})
        sog        = float(pr.get("Sog", 0.0))
        cog        = float(pr.get("Cog", 0.0))
        nav_status = int(pr.get("NavigationalStatus", 15))
        ship_type  = int(pr.get("ShipType", 0))
        name       = str(pr.get("Name", name)).strip() or name
    elif msg_type == "StandardClassBPositionReport":
        pr         = msg.get("StandardClassBPositionReport", {})
        sog        = float(pr.get("Sog", 0.0))
        cog        = float(pr.get("Cog", 0.0))
        nav_status = int(pr.get("NavigationalStatus", 15))
    else:
        return None

    if sog > 50:  sog = 0.0
    if cog > 360: cog = 0.0

    return {
        "mmsi": mmsi, "name": name,
        "lat": round(lat, 5), "lon": round(lon, 5),
        "sog": round(sog, 1), "cog": round(cog, 1),
        "heading": heading if heading <= 360 else int(cog),
        "nav_status": nav_status, "nav_label": NAV_STATUS.get(nav_status, "Unknown"),
        "ship_type": ship_type, "destination": destination,
        "imo": imo, "callsign": callsign, "zone": zone,
        "timestamp": ts, "msg_type": msg_type,
        "is_tanker": 80 <= ship_type <= 89,
    }


def _upsert_vessel(v: dict):
    mmsi = v["mmsi"]
    if v.get("ship_type", 0) != 0:
        _type_registry[mmsi] = v["ship_type"]
    if mmsi in _type_registry:
        v["ship_type"] = _type_registry[mmsi]
        v["is_tanker"] = 80 <= v["ship_type"] <= 89
    if mmsi in _vessels:
        existing = _vessels[mmsi]
        for key in ["name", "imo", "callsign", "destination"]:
            if not v.get(key) and existing.get(key):
                v[key] = existing[key]
    _vessels[mmsi] = v
    hist = _vessel_history.setdefault(mmsi, [])
    hist.append((v["timestamp"], v["lat"], v["lon"], v["sog"]))
    if len(hist) > 288:
        hist.pop(0)


# ── Demo loop ──────────────────────────────────────────────────────────────────
_NAMES = [
    "PERSIAN GLORY","GULF NAVIGATOR","HORMUZ STAR","ARABIAN CARRIER",
    "BANDAR IRAN","MUSANDAM SPIRIT","AL ZUBARA","FUJAIRAH PRIDE",
    "KHALIJ PIONEER","OMAN SEA TRADER","STRAIT RUNNER","QESHM VENTURE",
    "DIBA WAVE","BASRA EAGLE","TEHRAN VOYAGER","GULF CROWN",
    "ABU MUSA","HENDURABI","LAVAN SPIRIT","SIRRI CARRIER",
    "KISH EXPLORER","KHARK ISLAND","ADEN VOYAGER","RED SEA SPIRIT",
    "BALHAF CARRIER","DJIBOUTI TRADER","SUEZ EAGLE","CAPE RUNNER",
    "NORTH SEA TITAN","BOSPHORUS STAR","MALACCA QUEEN","ROTTERDAM EXPRESS",
    "SINGAPORE PRIDE","SUEZ GUARDIAN","CAPE HORN SPIRIT","BALTIC TRADER",
]
_PROFILES = [
    {"class":"VLCC",    "dwt":280000, "sog":14.2, "ship_type":80},
    {"class":"Suezmax", "dwt":155000, "sog":13.5, "ship_type":80},
    {"class":"Aframax", "dwt":110000, "sog":13.0, "ship_type":80},
    {"class":"LNG",     "dwt":85000,  "sog":17.5, "ship_type":84},
    {"class":"Product", "dwt":48000,  "sog":14.0, "ship_type":81},
    {"class":"Cargo",   "dwt":65000,  "sog":13.0, "ship_type":70},
]
_ZONE_SPAWNS = {
    "Hormuz":       [(26.5,56.5),(26.2,57.0),(25.8,56.8),(26.0,56.0)],
    "Persian Gulf": [(27.5,50.5),(26.0,52.0),(28.5,49.0),(25.0,53.5)],
    "Gulf of Oman": [(23.5,58.5),(22.0,60.0),(24.5,59.0),(21.5,61.0)],
    "Gulf of Aden": [(13.0,46.0),(12.5,48.0),(11.5,44.5)],
    "Red Sea":      [(18.0,40.5),(16.0,41.5),(20.0,39.5)],
    "Other":        [(51.5,3.0),(1.2,103.8),(35.0,139.0),(-34.0,18.5),(57.0,-37.0)],
}


def _demo_loop(api_key: str, stop: threading.Event):
    global _msg_count, _last_msg_time
    import random
    random.seed(None)
    _log("Demo: spawning global fleet...")
    fleet = []; name_pool = list(_NAMES); random.shuffle(name_pool)
    for zone, spawns in _ZONE_SPAWNS.items():
        for base_lat, base_lon in spawns:
            if not name_pool: break
            name = name_pool.pop(); p = random.choice(_PROFILES)
            lat  = base_lat + random.uniform(-0.3, 0.3)
            lon  = base_lon + random.uniform(-0.3, 0.3)
            nav  = random.choices([0,0,0,1,5], weights=[55,55,55,20,10])[0]
            sog  = max(0.0, (p["sog"] + random.gauss(0,1.0)) if nav==0 else 0.0)
            cog  = random.uniform(0, 360)
            fleet.append({
                "mmsi": f"41{random.randint(1000000,9999999)}", "name": name,
                "lat": lat, "lon": lon, "sog": round(sog,1), "cog": round(cog,1),
                "heading": round(cog,1), "nav_status": nav,
                "nav_label": NAV_STATUS.get(nav,"Unknown"),
                "ship_type": p["ship_type"], "vessel_class": p["class"], "dwt": p["dwt"],
                "is_tanker": 80<=p["ship_type"]<=89, "zone": zone,
                "destination": random.choice(["FUJAIRAH","BASRA","ROTTERDAM","SINGAPORE","",""]),
                "imo": f"IMO{random.randint(1000000,9999999)}",
                "callsign": f"A9{random.randint(100,999)}",
                "_cog": cog, "_sog_tgt": sog,
            })
    for v in fleet:
        pub = {k: val for k,val in v.items() if not k.startswith("_")}
        pub["timestamp"] = datetime.now(timezone.utc).isoformat()
        pub["msg_type"]  = "PositionReport"
        _upsert_vessel(pub); _msg_count += 1
    _last_msg_time = datetime.now(timezone.utc)
    _log(f"Demo: {len(fleet)} vessels across {len(_ZONE_SPAWNS)} zones")
    tick = 0
    while not stop.is_set():
        import random as _r; tick += 1
        for v in fleet:
            if _r.random() < 0.003:
                v["nav_status"] = _r.choices([0,1,5], weights=[65,25,10])[0]
                v["nav_label"]  = NAV_STATUS.get(v["nav_status"],"Unknown")
            if v["nav_status"]==0 and _r.random()<0.004: v["sog"] = _r.uniform(0.1,0.4)
            elif v["nav_status"]==0:
                v["sog"] = max(0, v["sog"]+(v["_sog_tgt"]-v["sog"])*0.1+_r.gauss(0,0.15))
            if v["nav_status"]==0 and v["sog"]>0.5:
                speed_dps = (v["sog"]*1852)/(3600*111320)
                rad = math.radians(v["_cog"]); step = speed_dps*8
                new_lat = v["lat"]+step*math.cos(rad)
                new_lon = v["lon"]+step*math.sin(rad)/max(math.cos(math.radians(v["lat"])),0.01)
                if not (-88<=new_lat<=88): v["_cog"]=(180-v["_cog"])%360; new_lat=v["lat"]
                if not (-179<=new_lon<=179): v["_cog"]=(360-v["_cog"])%360; new_lon=v["lon"]
                v["lat"]=round(new_lat,5); v["lon"]=round(new_lon,5)
                v["cog"]=round(v["_cog"],1); v["heading"]=v["cog"]
                v["zone"]=_classify_zone(v["lat"],v["lon"])
            pub={k:val for k,val in v.items() if not k.startswith("_")}
            pub["timestamp"]=datetime.now(timezone.utc).isoformat(); pub["msg_type"]="PositionReport"
            _upsert_vessel(pub)
        _msg_count+=len(fleet); _last_msg_time=datetime.now(timezone.utc)
        if tick%10==0: _log(f"Demo tick {tick}: {len(_vessels)} vessels")
        time.sleep(8)
