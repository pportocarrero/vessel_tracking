import streamlit as st
import pandas as pd
import time
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="Real-time Vessel Tracker",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS — Inter font scoped carefully so Streamlit icons still work
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Apply Inter only to the root app frame — Streamlit will cascade it down
   to text content. We explicitly EXCLUDE the sidebar toggle, expander
   chevrons, and any element that uses icon/symbol glyphs. */
[data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar content text — but NOT the collapse button itself */
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] .stCaption {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Metric text explicitly */
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Section headings and body text */
h1, h2, h3, h4, h5, p, td, th, caption {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Backgrounds */
[data-testid="stAppViewContainer"] { background: #080c14; }
[data-testid="stSidebar"] {
    background: #0a0e18;
    border-right: 1px solid #161d2e;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: #0f1623;
    border: 1px solid #1c2438;
    border-radius: 10px;
    padding: 14px 18px;
}
div[data-testid="stMetric"]:hover { border-color: #2a3654; }
div[data-testid="stMetricValue"] {
    color: #f0f4ff;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}
div[data-testid="stMetricLabel"] {
    color: #6b7a99;
    font-size: 0.68rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
div[data-testid="stMetricDelta"] { font-size: 0.78rem; }

.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
h1, h2, h3, h4 { color: #f0f4ff; letter-spacing: -0.02em; }
hr { border-color: #161d2e !important; }
.stButton > button { font-weight: 500; border-radius: 7px; }

/* Zone badge */
.zone-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    font-size: 0.82rem;
    font-weight: 500;
    color: #8892a4;
    border-bottom: 1px solid #161d2e;
}
.zone-badge:last-child {
    border-bottom: none;
}
.zone-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.section-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #4a5568;
    margin-bottom: 6px;
}

/* Remove Streamlit's bottom padding after the zones markdown block */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
    line-height: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] div {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
</style>
""", unsafe_allow_html=True)

AIS_KEY = "1efe0b9c2c3fe0fab4ede3da9473a1627ebc4d01"
EIA_KEY = "Mlh5ISF3daQcsjmbsKhziJhcGVmkosp5r7Vu8GUs"

for key, default in [
    ("stream_active", False),
    ("oil_prices", []),
    ("last_price_fetch", None),
    ("stats_history", []),
    ("alerts", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

import utils.ais_client as ais
from utils.eia_client import fetch_oil_prices
from utils.anomaly import detect_anomalies
from components.map_view import render_map
from components.metrics import render_metrics
from components.correlation import render_correlation
from components.vessel_table import render_vessel_table
from components.alerts_panel import render_alerts
from components.crisis_panel import render_crisis_panel

# Sidebar
with st.sidebar:
    st.markdown(
        "<div style='padding:4px 0 12px 0;"
        "font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;"
        "font-size:1.05rem;font-weight:600;color:#f0f4ff;letter-spacing:-0.01em'>"
        "🛢️ Vessel Tracker</div>",
        unsafe_allow_html=True,
    )

    stream_running = ais.is_running()
    if not stream_running:
        if st.button("▶ Start Live Feed", type="primary", use_container_width=True):
            ais.start_stream(api_key=AIS_KEY, demo_mode=False)
            st.session_state.stream_active = True
            st.rerun()
        #if st.button("🎭 Demo Mode", use_container_width=True):
        #    ais.start_stream(api_key="DEMO", demo_mode=True)
        #    st.session_state.stream_active = True
        #    st.rerun()
    else:
        st.success("🟢 Stream active")
        st.caption(f"Raw frames: {ais.get_raw_msg_count():,}")
        st.caption(f"Vessels: {len(ais.get_vessels()):,}")
        last_msg = ais.get_last_msg_time()
        if last_msg:
            ago = int((datetime.now(timezone.utc) - last_msg).total_seconds())
            st.caption(f"Last msg: {ago}s ago")
        if st.button("⏹ Stop Feed", use_container_width=True):
            ais.stop_stream()
            st.session_state.stream_active = False
            st.rerun()

    st.divider()
    anomaly_thresh = st.slider("Anomaly threshold (kn)", 0.1, 3.0, 0.5, 0.1)
    refresh_rate   = st.selectbox("Refresh every", [5, 10, 30, 60], index=1,
                                  format_func=lambda x: f"{x}s")

    st.divider()
    st.markdown("""
<div style='margin-bottom:0;padding-bottom:0'>
  <div class='section-label'>Monitoring Zones</div>
  <div style='display:flex;flex-direction:column;gap:0;margin-bottom:0'>
    <div class='zone-badge'><div class='zone-dot' style='background:#ef5350'></div>Strait of Hormuz <span style='color:#2d3a52;font-size:0.7rem;margin-left:auto'>ref</span></div>
    <div class='zone-badge'><div class='zone-dot' style='background:#ffa726'></div>Persian Gulf</div>
    <div class='zone-badge'><div class='zone-dot' style='background:#42a5f5'></div>Gulf of Oman</div>
    <div class='zone-badge'><div class='zone-dot' style='background:#26c06e'></div>Gulf of Aden</div>
    <div class='zone-badge' style='border-bottom:none'><div class='zone-dot' style='background:#ce93d8'></div>Red Sea</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.divider()
    with st.expander("🔧 Debug"):
        raw    = ais.get_raw_msg_count()
        parsed = ais.get_msg_count()
        unique = len(ais.get_vessels())
        st.markdown(f"""
| | Count |
|--|--|
| Raw frames | **{raw:,}** |
| Accepted msgs | **{parsed:,}** |
| Unique vessels | **{unique:,}** |
""")
        for entry in ais.get_debug_log()[:30]:
            st.caption(entry)

# Vessel data — filter to tankers/cargo at the DataFrame level
raw_vessels = ais.get_vessels()
if raw_vessels:
    vessels_df = pd.DataFrame(list(raw_vessels.values()))
    for col in ["lat", "lon", "sog", "cog", "nav_status", "ship_type"]:
        if col in vessels_df.columns:
            vessels_df[col] = pd.to_numeric(vessels_df[col], errors="coerce")
    vessels_df = vessels_df.dropna(subset=["lat", "lon"])
    # Apply tanker/cargo filter here — types 70-89 (cargo+tankers) + 0 (unknown pending static data)
    if "ship_type" in vessels_df.columns:
        tanker_mask = vessels_df["ship_type"].isin(set(range(70, 90)) | {0})
        vessels_df  = vessels_df[tanker_mask].reset_index(drop=True)
else:
    vessels_df = pd.DataFrame()

# Oil prices
now = datetime.now(timezone.utc)
if (st.session_state.last_price_fetch is None or
        (now - st.session_state.last_price_fetch).total_seconds() > 300):
    prices = fetch_oil_prices(api_key=EIA_KEY, demo_mode=False)
    if prices:
        st.session_state.oil_prices = prices
        st.session_state.last_price_fetch = now

# Anomaly detection
if raw_vessels:
    new_alerts = detect_anomalies(
        vessels={k: v for k, v in raw_vessels.items()
                 if v.get("ship_type", 0) in set(range(70, 90)) | {0}},
        vessel_history=ais.get_vessel_history(),
        sog_threshold=anomaly_thresh,
    )
    existing_ids = {x["id"] for x in st.session_state.alerts}
    for a in new_alerts:
        if a["id"] not in existing_ids:
            st.session_state.alerts.insert(0, a)
    st.session_state.alerts = st.session_state.alerts[:50]

# Stats snapshot
if not vessels_df.empty and "nav_status" in vessels_df.columns:
    n_underway = int((vessels_df["nav_status"] == 0).sum())
    n_holding = int(vessels_df["nav_status"].isin([1, 2, 5, 6]).sum())
    n_aden = int(vessels_df["zone"].isin(["Gulf of Aden","Red Sea"]).sum()) if "zone" in vessels_df.columns else 0
    wti_now = st.session_state.oil_prices[-1].get("wti") if st.session_state.oil_prices else None
    brent_now = st.session_state.oil_prices[-1].get("brent") if st.session_state.oil_prices else None
    st.session_state.stats_history.append({
        "ts": now, "total": len(vessels_df),
        "underway": n_underway, "holding": n_holding, "aden": n_aden,
        "wti": wti_now, "brent": brent_now,
    })
    cutoff = now - timedelta(hours=24)
    st.session_state.stats_history = [
        s for s in st.session_state.stats_history if s["ts"] > cutoff
    ]

# Layout
st.markdown(
    "<h2 style='font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;"
    "color:#f0f4ff;margin:0;font-weight:600;letter-spacing:-0.02em;font-size:1.6rem;margin-top:15px'>"
    "Real-time Vessel Tracker</h2>"
    "<p style='color:#4a5568;font-size:0.78rem;margin:3px 0 10px 0'>"
    "Global AIS &nbsp;·&nbsp; "
    "Middle East zones highlighted</p>",
    unsafe_allow_html=True,
)

status_col, refresh_col = st.columns([5, 1])
with status_col:
    render_crisis_panel(coverage_status=ais.get_coverage_status(), stream_running=stream_running)
with refresh_col:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

st.divider()

render_metrics(vessels_df=vessels_df, oil_prices=st.session_state.oil_prices, alerts=st.session_state.alerts)

st.divider()

map_col, alert_col = st.columns([3, 1])
with map_col:
    st.markdown('<div class="section-label">Live Vessel Map</div>', unsafe_allow_html=True)
    render_map(vessels_df=vessels_df)
with alert_col:
    st.markdown('<div class="section-label">Anomaly Alerts</div>', unsafe_allow_html=True)
    render_alerts(alerts=st.session_state.alerts)

st.divider()
st.markdown('<div class="section-label">Vessel Traffic × Crude Oil Price</div>', unsafe_allow_html=True)
render_correlation(stats_history=st.session_state.stats_history, oil_prices=st.session_state.oil_prices)

st.divider()
st.markdown('<div class="section-label">Vessel Registry</div>', unsafe_allow_html=True)
render_vessel_table(vessels_df=vessels_df)

st.divider()
st.markdown(
    f"<p style='color:#FFFFFF;font-size:0.7rem;text-align:center'>"
    f"{now.strftime('%Y-%m-%d %H:%M:%S UTC')} · "
    f"Vessels: {len(vessels_df):,} · Frames: {ais.get_raw_msg_count():,} · "
    f"AIS: aisstream.io · Prices: EIA · Research use only · Created by Pedro Portocarrero</p>",
    unsafe_allow_html=True,
)

if ais.is_running():
    effective_refresh = 3 if ais.get_msg_count() < 20 else refresh_rate
    time.sleep(effective_refresh)
    st.rerun()
