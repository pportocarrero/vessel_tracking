"""Vessel registry table v3 — includes zone column."""
import streamlit as st
import pandas as pd

NAV_LABEL = {
    0:"🟢 Underway", 1:"🟡 Anchored", 2:"🔴 No Command", 3:"🟠 Restricted",
    4:"🔵 By Draught", 5:"🟣 Moored",  6:"🔴 Aground",   15:"⚫ Unknown"
}
TYPE_LABEL = {80:"Tanker",81:"Product",82:"Chemical",83:"LPG",84:"LNG",85:"Crude",89:"Tanker"}
ZONE_ICON  = {
    "Hormuz":"🔴", "Persian Gulf":"🟠", "Gulf of Oman":"🔵",
    "Gulf of Aden":"🟢", "Red Sea":"🟣", "Other":"⚫"
}


def render_vessel_table(vessels_df: pd.DataFrame):
    if vessels_df.empty:
        st.info("No vessel data yet — start the live feed.")
        return

    df = vessels_df.copy()
    df["Status"]   = df["nav_status"].map(lambda x: NAV_LABEL.get(int(x), f"Code {int(x)}"))
    df["Type"]     = df["ship_type"].map(lambda x: TYPE_LABEL.get(int(x), f"Type {int(x)}"))
    df["SOG (kn)"] = df["sog"].round(1)
    df["COG (°)"]  = df["cog"].round(0).astype(int)
    df["Lat"]      = df["lat"].round(4)
    df["Lon"]      = df["lon"].round(4)
    df["Last Seen"]= df["timestamp"].apply(lambda x: str(x)[11:19] if x else "—")

    if "zone" in df.columns:
        df["Zone"] = df["zone"].map(lambda z: f"{ZONE_ICON.get(z,'⚫')} {z}")
    else:
        df["Zone"] = "—"

    if "vessel_class" in df.columns:
        df["Class"] = df["vessel_class"].fillna(df["Type"])
    else:
        df["Class"] = df["Type"]

    if "destination" in df.columns:
        df["Dest"] = df["destination"].fillna("").replace("", "—")
    else:
        df["Dest"] = "—"

    display = df[["name","mmsi","Zone","Status","Class","SOG (kn)","COG (°)","Lat","Lon","Dest","Last Seen"]].rename(
        columns={"name":"Vessel","mmsi":"MMSI"}
    )

    # Filter row
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    with f1:
        search = st.text_input("🔍 Search", placeholder="Name or MMSI", label_visibility="collapsed")
    with f2:
        zones = ["All"] + sorted(df["zone"].dropna().unique().tolist()) if "zone" in df.columns else ["All"]
        zone_f = st.selectbox("Zone", zones, label_visibility="collapsed")
    with f3:
        status_f = st.selectbox("Status", ["All"] + list(NAV_LABEL.values()), label_visibility="collapsed")
    with f4:
        sort_col = st.selectbox("Sort by", ["SOG (kn)", "Zone", "Vessel", "Status"], label_visibility="collapsed")

    if search:
        display = display[
            display["Vessel"].str.contains(search, case=False, na=False) |
            display["MMSI"].str.contains(search, case=False, na=False)
        ]
    if zone_f != "All":
        display = display[display["Zone"].str.contains(zone_f, na=False)]
    if status_f != "All":
        display = display[display["Status"] == status_f]

    display = display.sort_values(sort_col, ascending=(sort_col != "SOG (kn)"))

    st.caption(f"Showing {len(display)} of {len(vessels_df)} vessels")
    st.dataframe(display, use_container_width=True, height=320, hide_index=True,
                 column_config={
                     "SOG (kn)": st.column_config.NumberColumn(format="%.1f"),
                     "COG (°)":  st.column_config.NumberColumn(format="%d°"),
                 })

    csv = display.to_csv(index=False)
    st.download_button(
        "⬇ Export CSV", csv,
        f"hormuz_vessels_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv"
    )
