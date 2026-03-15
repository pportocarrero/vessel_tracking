"""KPI metrics row v6 — global tracking with ME zone breakdown."""
import streamlit as st
import pandas as pd


def render_metrics(vessels_df: pd.DataFrame, oil_prices: list, alerts: list):
    total    = len(vessels_df)
    underway = int((vessels_df["nav_status"] == 0).sum()) if not vessels_df.empty and "nav_status" in vessels_df else 0
    holding  = int(vessels_df["nav_status"].isin([1,2,5,6]).sum()) if not vessels_df.empty and "nav_status" in vessels_df else 0
    high_alr = len([a for a in alerts if a.get("severity") == "HIGH"])

    me_total = hormuz_n = aden_n = 0
    if not vessels_df.empty and "zone" in vessels_df.columns:
        me_zones  = ["Hormuz","Persian Gulf","Gulf of Oman","Gulf of Aden","Red Sea"]
        me_total  = int(vessels_df["zone"].isin(me_zones).sum())
        hormuz_n  = int((vessels_df["zone"] == "Hormuz").sum())
        aden_n    = int(vessels_df["zone"].isin(["Gulf of Aden","Red Sea"]).sum())

    wti_val = wti_chg = brent_val = brent_chg = None
    if oil_prices and len(oil_prices) >= 2:
        wti_val    = oil_prices[-1].get("wti")
        brent_val  = oil_prices[-1].get("brent")
        wti_prev   = oil_prices[-2].get("wti")
        brent_prev = oil_prices[-2].get("brent")
        if wti_val   and wti_prev:   wti_chg   = round(wti_val   - wti_prev,   2)
        if brent_val and brent_prev: brent_chg = round(brent_val - brent_prev, 2)

    cols = st.columns(8)
    with cols[0]: st.metric("🌍 Global Vessels", total)
    with cols[1]: st.metric("🟢 Underway",        underway, f"{int(underway/total*100)}%" if total else None)
    with cols[2]: st.metric("🟡 Holding",         holding,  f"{int(holding/total*100)}%" if total else None, delta_color="inverse")
    with cols[3]: st.metric("🌊 ME Region",       me_total)
    with cols[4]: st.metric("🔴 In Hormuz",       hormuz_n)
    with cols[5]: st.metric("🟢 Aden/Red Sea",    aden_n)
    with cols[6]: st.metric("🛢️ WTI ($/bbl)",    f"${wti_val:.2f}"   if wti_val   else "—", f"{wti_chg:+.2f}"   if wti_chg   else None)
    with cols[7]: st.metric("🛢️ Brent ($/bbl)",  f"${brent_val:.2f}" if brent_val else "—", f"{brent_chg:+.2f}" if brent_chg else None)
