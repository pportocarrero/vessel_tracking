"""
Coverage status banner — minimal, clean.
No static reference data. Just live stream status.
"""

import streamlit as st


def render_crisis_panel(coverage_status: dict, stream_running: bool):
    status = coverage_status.get("status", "offline")
    color  = coverage_status.get("color", "#607d8b")
    label  = coverage_status.get("label", "")

    if not stream_running:
        return  # nothing to show if stream is off

    st.markdown(
        f'<div style="background:#1a1f2e;border-left:4px solid {color};border-radius:6px;'
        f'padding:10px 16px;margin-bottom:8px">'
        f'<span style="font-size:0.88rem;font-weight:600;color:{color}">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
