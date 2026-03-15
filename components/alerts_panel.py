"""Anomaly alerts panel."""
import streamlit as st

SEV_COLOR = {"HIGH":"#ef5350","MEDIUM":"#ffa726","LOW":"#26c06e"}
SEV_ICON  = {"HIGH":"🔴","MEDIUM":"🟡","LOW":"🟢"}


def render_alerts(alerts: list):
    if not alerts:
        st.markdown(
            '<div style="background:#1a1f2e;border:1px solid #2d3348;border-radius:8px;'
            'padding:20px;text-align:center;color:#5c6474;font-size:0.85rem">'
            '✓ No anomalies<br><span style="font-size:0.72rem">Monitoring active</span></div>',
            unsafe_allow_html=True)
        return

    high = sum(1 for a in alerts if a.get("severity") == "HIGH")
    med  = sum(1 for a in alerts if a.get("severity") == "MEDIUM")
    st.markdown(
        f'<div style="background:#1a1f2e;border:1px solid #2d3348;border-radius:6px;'
        f'padding:8px 12px;margin-bottom:8px;font-size:0.78rem">'
        f'<span style="color:#ef5350">🔴 {high} HIGH</span> &nbsp;'
        f'<span style="color:#ffa726">🟡 {med} MED</span></div>',
        unsafe_allow_html=True)

    for a in alerts[:15]:
        sev   = a.get("severity","LOW")
        color = SEV_COLOR.get(sev,"#607d8b")
        icon  = SEV_ICON.get(sev,"⚪")
        lat, lon = a.get("lat"), a.get("lon")
        pos   = f"{lat:.3f}°N {lon:.3f}°E" if lat and lon else ""
        st.markdown(
            f'<div style="background:#1a1f2e;border-left:3px solid {color};border-radius:5px;'
            f'padding:9px 11px;margin-bottom:5px">'
            f'<div style="display:flex;justify-content:space-between">'
            f'<span style="color:{color};font-weight:700;font-size:0.78rem">{icon} {a["type"]}</span>'
            f'<span style="color:#5c6474;font-size:0.7rem">{a["timestamp"]}</span></div>'
            f'<div style="color:#ffd54f;font-size:0.78rem;font-weight:600">{a["name"]}</div>'
            f'<div style="color:#b0bec5;font-size:0.73rem;line-height:1.4">{a["message"]}</div>'
            f'{f"<div style=\'color:#5c6474;font-size:0.7rem;margin-top:3px\'>📍 {pos}</div>" if pos else ""}'
            f'</div>',
            unsafe_allow_html=True)

    if len(alerts) > 15:
        st.caption(f"+ {len(alerts)-15} older")
