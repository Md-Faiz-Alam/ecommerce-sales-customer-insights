"""Shared data access, filters, chart styling and model helpers for the Streamlit app.

The app is self-contained: it reads only app/data/*.parquet and app/models/* (produced by
`python -m ecom.export_app`), so it deploys to Streamlit Community Cloud without the warehouse.
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
DATA = HERE / "data"
MODELS = HERE / "models"

# Same CVD-validated palette as the notebooks and Power BI theme.
BLUE, ORANGE, AQUA = "#2A78D6", "#EB6834", "#1BAF7A"
GREY = "#A3A29D"
SEQ = ["#CDE2FB", "#9EC5F4", "#6DA7EC", "#3987E5", "#256ABF", "#184F95", "#0D366B"]

ROUTE_COLS = [
    "route_prior_orders", "route_delivery_days", "route_delivery_days_90d",
    "route_late_rate", "route_late_rate_90d",
]  # fmt: skip

TIMING_BUCKETS = [
    (-999, -8, "8+ days early"),
    (-7, -1, "1–7 days early"),
    (0, 0, "On promised day"),
    (1, 3, "1–3 days late"),
    (4, 7, "4–7 days late"),
    (8, 999, "8+ days late"),
]


# ----------------------------------------------------------------------------- data
@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


@st.cache_data
def meta() -> dict:
    return json.loads((MODELS / "meta.json").read_text())


@st.cache_resource
def booster(name: str) -> lgb.Booster:
    return lgb.Booster(model_file=str(MODELS / f"{name}.txt"))


def brl(x: float) -> str:
    """Compact enough for a KPI tile: R$15.4M, R$352K, R$160."""
    if abs(x) >= 1e6:
        return f"R${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"R${x / 1e3:,.0f}K"
    return f"R${x:,.0f}"


# ----------------------------------------------------------------------------- filters
def sidebar_filters() -> None:
    """Rendered once in the entry script, so the selection persists across pages."""
    orders = load("orders")
    lo, hi = orders["purchase_date"].min().date(), orders["purchase_date"].max().date()
    st.sidebar.header("Filters")
    st.sidebar.caption("Apply to the analytics pages")
    st.sidebar.date_input(
        "Purchase date", value=(lo, hi), min_value=lo, max_value=hi, key="f_dates"
    )
    st.sidebar.multiselect(
        "Customer state", sorted(orders["customer_state"].cat.categories), key="f_states"
    )
    st.sidebar.multiselect("Category", sorted(orders["category"].cat.categories), key="f_cats")


def filtered_orders() -> pd.DataFrame:
    df = load("orders")
    dates = st.session_state.get("f_dates")
    if isinstance(dates, tuple | list) and len(dates) == 2:
        df = df[df["purchase_date"].between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
    if st.session_state.get("f_states"):
        df = df[df["customer_state"].isin(st.session_state["f_states"])]
    if st.session_state.get("f_cats"):
        df = df[df["category"].isin(st.session_state["f_cats"])]
    return df


def require_rows(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("No orders match the current filters. Widen the date range or clear a filter.")
        st.stop()


def timing_bucket(delay: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=delay.index, dtype="object")
    for lo, hi, label in TIMING_BUCKETS:
        out[delay.between(lo, hi)] = label
    return pd.Categorical(out, categories=[b[2] for b in TIMING_BUCKETS], ordered=True)


# ----------------------------------------------------------------------------- charts
def style(
    fig: go.Figure, height: int = 360, pct_y: bool = False, money_y: bool = False
) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(family="Segoe UI, system-ui, sans-serif"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=0.5, rangemode="tozero")
    if pct_y:
        fig.update_yaxes(tickformat=".0%")
    if money_y:
        fig.update_yaxes(tickprefix="R$", tickformat="~s")
    return fig


def takeaway(text: str) -> None:
    """Chart title = the insight, not the field name."""
    st.markdown(f"**{text}**")


# ----------------------------------------------------------------------------- model input
def feature_frame(values: dict, features: list[str]) -> pd.DataFrame:
    """One-row frame in training column order, with the training categories."""
    cats = meta()["categories"]
    row = {}
    for f in features:
        if f in cats:
            row[f] = pd.Categorical([values[f]], categories=cats[f])
        else:
            row[f] = [float(values[f])]
    return pd.DataFrame(row)[features]


def predict_quantiles(X: pd.DataFrame) -> dict[float, float]:
    qs = meta()["quantiles"]
    preds = np.array([booster(f"delivery_p{q * 1000:.0f}").predict(X)[0] for q in qs])
    preds = np.maximum.accumulate(np.maximum(preds, 0))  # no quantile crossing
    return dict(zip(qs, preds, strict=True))
