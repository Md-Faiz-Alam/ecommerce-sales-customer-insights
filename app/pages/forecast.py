import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

st.title("Demand Forecast")
st.caption(
    "28-day daily order forecast for carrier capacity planning: an ensemble of ETS and a 4-week seasonal mean, "
    "chosen by rolling-origin backtest (4 folds × 28 days)."
)

hist = lib.load("daily_orders")
fut = lib.load("forecast")
recent = hist[hist["day"] >= hist["day"].max() - pd.Timedelta(days=90)]

cols = st.columns(3)
cols[0].metric("Forecast, next 28 days", f"{fut['forecast'].sum():,.0f} orders")
cols[1].metric("Last 28 days (actual)", f"{hist['orders'].tail(28).sum():,.0f} orders")
best = next(r for r in lib.meta()["forecast_summary"] if r["model"].startswith("Ensemble"))
cols[2].metric("Backtest: avg 28-day volume error", f"{best['total_28d_abs_err_pct']:.1f}%")

lib.takeaway("Next 28 days, with an 80% interval")
fig = go.Figure()
fig.add_scatter(
    x=recent["day"], y=recent["orders"], name="Actual", line=dict(color=lib.GREY, width=1.5)
)
fig.add_scatter(
    x=fut["day"], y=fut["high_80"], line=dict(width=0), showlegend=False, hoverinfo="skip"
)
fig.add_scatter(x=fut["day"], y=fut["low_80"], fill="tonexty", fillcolor="rgba(42,120,214,0.15)",
                line=dict(width=0), name="80% interval", hoverinfo="skip")  # fmt: skip
fig.add_scatter(
    x=fut["day"], y=fut["forecast"], name="Forecast", line=dict(color=lib.BLUE, width=2.5)
)
st.plotly_chart(lib.style(fig, height=380).update_layout(yaxis_title="Orders per day"))

left, right = st.columns([3, 2])
with left:
    lib.takeaway("Backtest: the ensemble beats every baseline, especially in the worst month")
    summary = pd.DataFrame(lib.meta()["forecast_summary"]).set_index("model")
    summary = summary.rename(columns={
        "mae": "MAE (orders/day)", "mape_pct": "MAPE %", "mase": "MASE",
        "total_28d_abs_err_pct": "28-day total error %", "total_28d_worst_err_pct": "Worst 28-day error %",
    })  # fmt: skip
    st.dataframe(summary.style.format("{:.1f}"))
with right:
    lib.takeaway("Weekly totals to book")
    weekly = fut.set_index("day").resample("7D", origin=fut["day"].min()).sum().round(0)
    weekly.index = [f"{d:%d %b} – {d + pd.Timedelta(days=6):%d %b}" for d in weekly.index]
    st.dataframe(
        weekly.rename(columns={"forecast": "Forecast", "low_80": "Low", "high_80": "High"})
    )

st.info(
    "Demand here is dominated by shocks (Black Friday 2017: 1,176 orders in a day; the May 2018 truckers' strike), "
    "which no history-only model can foresee. In production, add an **event calendar** as manual overrides, "
    "and book capacity at the upper band for peak weeks."
)
