"""
Correlation chart v3 — simplified.
Shows: WTI price line + Brent price line + vessel count bars (holding + underway).
NO Pearson correlation panel.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def render_correlation(stats_history: list, oil_prices: list):
    has_live = len(stats_history) >= 2

    if has_live:
        _live_chart(stats_history)
    else:
        _price_only_chart(oil_prices)


def _live_chart(stats_history: list):
    df = pd.DataFrame(stats_history)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts")

    has_price   = df["wti"].notna().sum() > 1
    has_traffic = df["holding"].notna().sum() > 1

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        row_heights=[0.55, 0.45],
    )

    # ── Panel 1: Oil prices ────────────────────────────────────────────────────
    if has_price:
        fig.add_trace(go.Scatter(
            x=df["ts"], y=df["wti"],
            name="WTI Crude",
            line=dict(color="#42a5f5", width=2.5),
            hovertemplate="WTI: $%{y:.2f}<extra></extra>",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["ts"], y=df["brent"],
            name="Brent Crude",
            line=dict(color="#ffd54f", width=2.5, dash="dot"),
            hovertemplate="Brent: $%{y:.2f}<extra></extra>",
        ), row=1, col=1)

        # Spread fill
        if df["brent"].notna().any() and df["wti"].notna().any():
            fig.add_trace(go.Scatter(
                x=pd.concat([df["ts"], df["ts"][::-1]]),
                y=pd.concat([df["brent"], df["wti"][::-1]]),
                fill="toself",
                fillcolor="rgba(255,213,79,0.07)",
                line=dict(color="rgba(0,0,0,0)"),
                name="Brent–WTI Spread",
                hoverinfo="skip",
            ), row=1, col=1)

    # ── Panel 2: Vessel traffic ────────────────────────────────────────────────
    if has_traffic:
        fig.add_trace(go.Bar(
            x=df["ts"], y=df["holding"],
            name="Holding / Anchored",
            marker_color="#ffd54f",
            opacity=0.85,
            hovertemplate="Holding: %{y}<extra></extra>",
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df["ts"], y=df["underway"],
            name="Underway",
            fill="tozeroy",
            fillcolor="rgba(38,192,110,0.12)",
            line=dict(color="#26c06e", width=2),
            hovertemplate="Underway: %{y}<extra></extra>",
        ), row=2, col=1)

        # Zone breakdown lines if available
        if "aden" in df.columns and df["aden"].notna().sum() > 1:
            fig.add_trace(go.Scatter(
                x=df["ts"], y=df["aden"],
                name="Gulf of Aden / Red Sea",
                line=dict(color="#26c06e", width=1.5, dash="dot"),
                hovertemplate="Aden/Red Sea: %{y}<extra></extra>",
            ), row=2, col=1)

    fig.update_layout(
        height=500,
        plot_bgcolor="#080c14", paper_bgcolor="#080c14",
        font=dict(color="#8892a4", family="Inter,-apple-system,sans-serif", size=11),
        legend=dict(
            orientation="h",
            x=0, y=-0.12,          # below the chart, no overlap
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        hovermode="x unified",
        margin=dict(t=20, b=80, l=65, r=20),  # t=20: no title, b=80: room for legend
        barmode="overlay",
    )
    fig.update_xaxes(gridcolor="#1e2333", showgrid=True)
    fig.update_yaxes(gridcolor="#1e2333", showgrid=True)
    fig.update_yaxes(title_text="USD / bbl",    row=1, col=1,
                     title_font=dict(size=10, color="#6b7a99"))
    fig.update_yaxes(title_text="Vessel count",  row=2, col=1,
                     title_font=dict(size=10, color="#6b7a99"))
    # Panel labels via annotations (no overlap with legend)
    fig.add_annotation(text="Crude Oil Spot Price (USD/bbl)",
        xref="paper", yref="paper", x=0, y=1.01, xanchor="left",
        showarrow=False, font=dict(size=11, color="#8892a4"))
    fig.add_annotation(text="Vessel Traffic — All Zones",
        xref="paper", yref="paper", x=0, y=0.42, xanchor="left",
        showarrow=False, font=dict(size=11, color="#8892a4"))

    st.plotly_chart(fig, use_container_width=True)

    # Summary caption
    if has_price and has_traffic and not df.empty:
        latest = df.iloc[-1]
        wti    = latest.get("wti")
        brent  = latest.get("brent")
        hold   = latest.get("holding", 0)
        under  = latest.get("underway", 0)
        if wti and brent:
            spread = round(brent - wti, 2)
            st.caption(
                f"Latest — WTI: **${wti:.2f}** · Brent: **${brent:.2f}** · "
                f"Spread: **${spread:.2f}** · "
                f"Vessels underway: **{int(under)}** · Holding: **{int(hold)}**"
            )


def _price_only_chart(oil_prices: list):
    if not oil_prices:
        st.info("▶ Start the live feed to begin receiving data.")
        return

    df = pd.DataFrame(oil_prices)
    df["date"] = pd.to_datetime(df["date"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["wti"],
        name="WTI Crude",
        line=dict(color="#42a5f5", width=2.5),
        fill="tozeroy", fillcolor="rgba(66,165,245,0.07)",
        hovertemplate="WTI: $%{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["brent"],
        name="Brent Crude",
        line=dict(color="#ffd54f", width=2.5, dash="dot"),
        hovertemplate="Brent: $%{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        height=300,
        plot_bgcolor="#080c14", paper_bgcolor="#080c14",
        font=dict(color="#8892a4", family="Inter,-apple-system,sans-serif", size=11),
        legend=dict(orientation="h", x=0, y=-0.18, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        margin=dict(t=20, b=70, l=65, r=20),
        yaxis_title="USD / bbl",
    )
    fig.add_annotation(text="WTI &amp; Brent Spot Price — Last 90 Days (EIA)",
        xref="paper", yref="paper", x=0, y=1.04, xanchor="left",
        showarrow=False, font=dict(size=11, color="#8892a4"))
    fig.update_xaxes(gridcolor="#1e2333")
    fig.update_yaxes(gridcolor="#1e2333")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("▶ Start the live feed to overlay vessel traffic data.")
