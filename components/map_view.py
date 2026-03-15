"""
Interactive Folium map v8 — dark mode, global vessels, ME zone overlays.
"""

import folium
from folium.plugins import MiniMap, Fullscreen, MarkerCluster
import streamlit as st
from streamlit_folium import st_folium
import pandas as pd

MAP_CENTER = [20.0, 50.0]
MAP_ZOOM   = 4

STATUS_COLOR = {
    0: "#26c06e",  # underway — green
    1: "#ffd54f",  # anchored — amber
    2: "#ef5350",  # no command — red
    3: "#ff8f00",  # restricted — orange
    4: "#42a5f5",  # by draught — blue
    5: "#7e57c2",  # moored — purple
    6: "#ef5350",  # aground — red
    15: "#455a7a", # unknown — muted blue
}
STATUS_LABEL = {
    0:"Underway", 1:"Anchored", 2:"No Command", 3:"Restricted",
    4:"By Draught", 5:"Moored", 6:"Aground", 15:"Unknown"
}

ZONE_BOXES = [
    ([22.0, 54.5, 27.5, 61.0], "#ef5350", "Strait of Hormuz", "4 4"),
    ([23.5, 47.5, 30.5, 56.5], "#ffa726", "Persian Gulf",     "4 4"),
    ([20.5, 55.5, 26.0, 62.5], "#42a5f5", "Gulf of Oman",     "4 4"),
    ([10.5, 42.5, 16.0, 51.5], "#26c06e", "Gulf of Aden",     "4 4"),
    ([12.5, 38.0, 22.5, 44.5], "#ce93d8", "Red Sea",          "4 4"),
]

KEY_PORTS = [
    (26.56, 56.25, "Hormuz Strait"),
    (27.18, 56.27, "Bandar Abbas"),
    (25.20, 55.27, "Dubai"),
    (23.58, 58.59, "Muscat"),
    (29.37, 47.98, "Kuwait"),
    (11.60, 43.14, "Djibouti"),
    (12.78, 45.01, "Aden"),
    (21.49, 39.17, "Jeddah"),
]


def render_map(vessels_df: pd.DataFrame):
    m = folium.Map(
        location=MAP_CENTER,
        zoom_start=MAP_ZOOM,
        tiles=None,
        prefer_canvas=True,
    )

    # ── Dark tile (default) ────────────────────────────────────────────────────
    # OSM added first so it appears in layer switcher but is NOT the default
    folium.TileLayer("OpenStreetMap", name="Street Map", show=False).add_to(m)

    # Dark tiles added last = active by default in Folium
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; OSM &copy; CARTO',
        name="Dark (labels)",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com">CARTO</a>',
        name="Dark (default)",
        max_zoom=19,
        show=True,
    ).add_to(m)

    # ── Zone boxes ─────────────────────────────────────────────────────────────
    for (sw_lat, sw_lon, ne_lat, ne_lon), color, label, dash in ZONE_BOXES:
        folium.Rectangle(
            bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
            color=color,
            weight=1.2,
            fill=True,
            fill_color=color,
            fill_opacity=0.05,
            dash_array=dash,
            tooltip=label,
        ).add_to(m)
        folium.Marker(
            [ne_lat - 0.4, sw_lon + 0.5],
            icon=folium.DivIcon(
                html=(
                    f'<div style="font-size:9px;color:{color};font-weight:600;'
                    f'white-space:nowrap;text-shadow:0 1px 3px rgba(0,0,0,0.9);'
                    f'font-family:Inter,sans-serif;letter-spacing:0.04em">{label}</div>'
                ),
                icon_size=(0, 0),
            )
        ).add_to(m)

    # ── Port labels ────────────────────────────────────────────────────────────
    for lat, lon, label in KEY_PORTS:
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(
                html=(
                    f'<div style="font-size:8px;color:#4a5568;white-space:nowrap;'
                    f'font-family:Inter,sans-serif;text-shadow:0 1px 2px rgba(0,0,0,0.8)">'
                    f'{label}</div>'
                ),
                icon_size=(0, 0),
            )
        ).add_to(m)

    # ── Vessels ────────────────────────────────────────────────────────────────
    if vessels_df.empty:
        folium.Marker(
            MAP_CENTER,
            icon=folium.DivIcon(
                html=(
                    '<div style="background:rgba(15,22,35,0.92);border:1px solid #1c2438;'
                    'border-radius:8px;padding:10px 14px;color:#6b7a99;font-size:12px;'
                    'white-space:nowrap;font-family:Inter,sans-serif;font-weight:500">'
                    '▶ Start Live Feed to see vessels</div>'
                ),
                icon_size=(0, 0), icon_anchor=(130, 20),
            ),
        ).add_to(m)
    else:
        cluster = MarkerCluster(
            options={
                "maxClusterRadius": 35,
                "disableClusteringAtZoom": 8,
                "spiderfyOnMaxZoom": True,
            }
        ).add_to(m)

        for _, row in vessels_df.iterrows():
            nav   = int(row.get("nav_status", 15))
            sog   = float(row.get("sog", 0.0))
            cog   = float(row.get("cog", 0.0))
            lat   = float(row["lat"])
            lon   = float(row["lon"])
            name  = str(row.get("name", "Unknown"))
            mmsi  = str(row.get("mmsi", ""))
            zone  = str(row.get("zone", ""))
            color = STATUS_COLOR.get(nav, "#455a7a")
            label = STATUS_LABEL.get(nav, "Unknown")

            # Arrow icon pointing in COG direction
            arrow_svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" '
                f'style="transform:rotate({cog}deg);transform-origin:center;display:block">'
                f'<polygon points="9,1 13,16 9,12 5,16" '
                f'fill="{color}" stroke="rgba(0,0,0,0.6)" stroke-width="0.8"/>'
                f'</svg>'
            )
            icon = folium.DivIcon(
                html=f'<div style="width:18px;height:18px">{arrow_svg}</div>',
                icon_size=(18, 18),
                icon_anchor=(9, 9),
            )

            # Popup
            ship_type_label = _ship_type_label(int(row.get("ship_type", 0)))
            dest = str(row.get("destination", "")).strip()
            popup_html = f"""
            <div style="background:#0a0e18;border:1px solid #1c2438;border-radius:10px;
                        padding:14px;font-family:Inter,sans-serif;min-width:200px;color:#e8eaf0">
              <div style="font-weight:700;color:#ffd54f;font-size:13px;
                          margin-bottom:8px;letter-spacing:-0.01em">🚢 {name}</div>
              <table style="font-size:11px;line-height:2;width:100%;border-collapse:collapse">
                <tr><td style="color:#4a5568;padding-right:10px">MMSI</td><td style="color:#c8d0e0">{mmsi}</td></tr>
                <tr><td style="color:#4a5568">Zone</td><td style="color:#ffd54f;font-weight:600">{zone or "Global"}</td></tr>
                <tr><td style="color:#4a5568">Type</td><td style="color:#c8d0e0">{ship_type_label}</td></tr>
                <tr><td style="color:#4a5568">Status</td><td style="color:{color};font-weight:600">{label}</td></tr>
                <tr><td style="color:#4a5568">SOG</td><td style="color:#c8d0e0">{sog:.1f} kn</td></tr>
                <tr><td style="color:#4a5568">COG</td><td style="color:#c8d0e0">{cog:.0f}°</td></tr>
                <tr><td style="color:#4a5568">Position</td><td style="color:#c8d0e0">{lat:.4f}°N {lon:.4f}°E</td></tr>
                {f'<tr><td style="color:#4a5568">Dest</td><td style="color:#c8d0e0">{dest}</td></tr>' if dest else ''}
              </table>
            </div>"""

            folium.Marker(
                [lat, lon],
                icon=icon,
                tooltip=folium.Tooltip(
                    f"<span style='font-family:Inter,sans-serif'>"
                    f"<b>{name}</b><br>{zone or 'Global'} · {label} · {sog:.1f} kn</span>"
                ),
                popup=folium.Popup(popup_html, max_width=260),
            ).add_to(cluster)

    # ── Legend ─────────────────────────────────────────────────────────────────
    legend_html = """
    <div style="position:fixed;bottom:28px;left:28px;z-index:1000;
                background:rgba(8,12,20,0.93);
                border:1px solid #1c2438;border-radius:10px;
                padding:12px 16px;font-family:Inter,sans-serif;color:#e8eaf0;
                min-width:148px;backdrop-filter:blur(8px)">
      <div style="font-size:9px;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.1em;color:#4a5568;margin-bottom:8px">Vessel Status</div>
      <div style="font-size:11px;line-height:2">
        <span style="color:#26c06e">▶</span> Underway<br>
        <span style="color:#ffd54f">⚓</span> Anchored<br>
        <span style="color:#7e57c2">●</span> Moored<br>
        <span style="color:#ef5350">⚠</span> Stopped<br>
        <span style="color:#455a7a">?</span> Unknown
      </div>
      <div style="font-size:9px;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.1em;color:#4a5568;margin:10px 0 8px 0">ME Zones</div>
      <div style="font-size:11px;line-height:2">
        <span style="color:#ef5350">━</span> Hormuz<br>
        <span style="color:#ffa726">━</span> Persian Gulf<br>
        <span style="color:#42a5f5">━</span> Gulf of Oman<br>
        <span style="color:#26c06e">━</span> Gulf of Aden<br>
        <span style="color:#ce93d8">━</span> Red Sea
      </div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    MiniMap(toggle_display=True, tile_layer="CartoDB dark_matter").add_to(m)
    Fullscreen(position="topright").add_to(m)
    folium.LayerControl(position="topright").add_to(m)

    st_folium(m, width="100%", height=700, returned_objects=[])


def _ship_type_label(t: int) -> str:
    if 80 <= t <= 89:
        labels = {80:"Tanker",81:"Tanker — Haz A",82:"Tanker — Haz B",
                  83:"Tanker — Haz C",84:"LNG Carrier",85:"Tanker — Haz E",89:"Tanker"}
        return labels.get(t, f"Tanker ({t})")
    if 70 <= t <= 79:
        return "Cargo"
    return f"Type {t}" if t else "Unknown"
