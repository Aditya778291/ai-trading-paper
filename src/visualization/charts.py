from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def create_candlestick_chart(
    df: pd.DataFrame,
    indicators: list[str] | None = None,
    show_bollinger: bool = False,
) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="OHLC",
    ))

    for indicator in indicators or []:
        if indicator in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[indicator],
                mode="lines",
                name=indicator,
            ))

    if show_bollinger:
        for column in ("BB_UPPER", "BB_MIDDLE", "BB_LOWER"):
            if column in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df[column],
                    mode="lines",
                    name=column,
                ))

    fig.update_layout(
        title="Price Chart",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_volume_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df.index,
        y=df["Volume"],
        name="Volume",
    ))
    fig.update_layout(
        title="Volume",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_rsi_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["RSI_14"],
        mode="lines",
        name="RSI 14",
    ))
    fig.add_hline(y=70, line_dash="dash", annotation_text="70")
    fig.add_hline(y=30, line_dash="dash", annotation_text="30")
    fig.update_layout(
        title="Relative Strength Index (RSI)",
        yaxis=dict(range=[0, 100]),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_macd_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD"], mode="lines", name="MACD"
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD_SIGNAL"], mode="lines", name="Signal"
    ))
    fig.add_trace(go.Bar(
        x=df.index, y=df["MACD_HIST"], name="Histogram"
    ))
    fig.update_layout(
        title="MACD",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_normalized_comparison_chart(series_map: dict[str, pd.Series]):
    fig = go.Figure()
    for name, series in series_map.items():
        clean = series.dropna()
        if clean.empty:
            continue
        normalized = clean / clean.iloc[0] * 100
        fig.add_trace(go.Scatter(x=normalized.index, y=normalized,
                                 mode="lines", name=name))
    fig.update_layout(title="Normalized Performance Comparison (Start = 100)",
                      hovermode="x unified",
                      margin=dict(l=20, r=20, t=50, b=20))
    return fig
