"""Anomaly detection for vessel behaviour in the Strait of Hormuz."""

import math
from datetime import datetime, timezone


def detect_anomalies(vessels: dict, vessel_history: dict, sog_threshold: float = 0.5) -> list[dict]:
    alerts = []
    now = datetime.now(timezone.utc)

    for mmsi, v in vessels.items():
        hist = vessel_history.get(mmsi, [])
        if len(hist) < 3:
            continue

        recent_sogs = [h[3] for h in hist[-6:] if h[3] is not None]
        if len(recent_sogs) < 2:
            continue

        avg_sog     = sum(recent_sogs[:-1]) / max(len(recent_sogs) - 1, 1)
        current_sog = v.get("sog", 0.0)

        # Sudden stop
        if avg_sog > 4.0 and current_sog < sog_threshold:
            alerts.append(_alert(mmsi, v, "SUDDEN STOP", "HIGH",
                f"Was {avg_sog:.1f}kn → now {current_sog:.1f}kn. Possible AIS spoofing or deliberate hold.", now))
            continue

        # Speed drop >60%
        if avg_sog > 6.0 and sog_threshold <= current_sog < avg_sog * 0.4:
            alerts.append(_alert(mmsi, v, "SPEED DROP", "MEDIUM",
                f"Speed dropped {int((1-current_sog/avg_sog)*100)}% from ~{avg_sog:.1f}kn to {current_sog:.1f}kn.", now))
            continue

        # Positional jump
        if len(hist) >= 2:
            dist = _haversine(hist[-2][1], hist[-2][2], v["lat"], v["lon"])
            if dist > 80:
                alerts.append(_alert(mmsi, v, "POSITIONAL JUMP", "HIGH",
                    f"Position jumped {dist:.0f}km. Possible AIS spoofing or gap.", now))

    return alerts


def _alert(mmsi, v, atype, severity, message, ts):
    return {
        "id":       f"{mmsi}-{atype}-{ts.strftime('%H%M%S')}",
        "mmsi":     mmsi,
        "name":     v.get("name", mmsi),
        "type":     atype,
        "severity": severity,
        "message":  message,
        "lat":      v.get("lat"),
        "lon":      v.get("lon"),
        "timestamp": ts.strftime("%H:%M:%S UTC"),
        "ts_obj":   ts,
    }


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    d = math.radians
    a = math.sin((d(lat2)-d(lat1))/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin((d(lon2)-d(lon1))/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
