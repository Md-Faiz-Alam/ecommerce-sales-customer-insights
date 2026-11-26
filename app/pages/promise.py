import math

import lib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from order_form import order_form

st.title("Delivery Promise Simulator")
st.caption(
    "A LightGBM quantile model predicts how long *this* order will take, then sets a promise per order. "
    "Olist uses one padded buffer for everyone (~24 days promised for ~12.5 delivered)."
)

m = lib.meta()
values, route = order_form("promise")

policies = {
    f"Reliability: P{m['chosen_quantile'] * 100:g} (chosen on validation)": m["chosen_quantile"],
    "Balanced: P90": 0.9,
    "Growth (shorter promises): P85": 0.85,
}
policy = st.radio("Promise policy", list(policies), horizontal=True)
q = policies[policy]

X = lib.feature_frame(values, m["purchase_features"])
preds = lib.predict_quantiles(X)
promise = max(1, math.ceil(preds[q]))
olist_promise = math.ceil(route["estimated_delivery_days"])

st.divider()
cols = st.columns(4)
diff = promise - olist_promise
cols[0].metric("Recommended promise", f"{promise} days",
               delta=f"{diff:+d} day{'' if abs(diff) == 1 else 's'} vs Olist", delta_color="inverse")  # fmt: skip
cols[1].metric("Olist's usual promise (route)", f"{olist_promise} days")
cols[2].metric("Most likely delivery (P50)", f"{preds[0.5]:.1f} days")
cols[3].metric("Route's typical delivery", f"{route['actual_days_median']:.0f} days",
               help=f"Median over {int(route['orders']):,} historical orders on {route['route']}")  # fmt: skip

ladder = pd.DataFrame({"days": list(preds.values()), "chance": list(preds.keys())})
lib.takeaway("Chance this order has arrived by day X (model quantiles)")
fig = px.line(ladder, x="days", y="chance", markers=True, color_discrete_sequence=[lib.BLUE])
fig.update_traces(hovertemplate="by day %{x:.1f}: %{y:.1%} chance<extra></extra>")
fig.add_vline(x=promise, line_color=lib.BLUE, line_dash="dash",
              annotation_text=f"model promise {promise}d", annotation_position="top left")  # fmt: skip
fig.add_vline(x=olist_promise, line_color=lib.ORANGE, line_dash="dash",
              annotation_text=f"Olist {olist_promise}d", annotation_position="bottom right")  # fmt: skip
fig = lib.style(fig, height=340, pct_y=True).update_layout(
    xaxis_title="Days after purchase", yaxis_title=None
)
st.plotly_chart(fig.update_xaxes(rangemode="tozero"))

with st.expander("How good is this model? (tested on unseen months, Jun–Aug 2018)"):
    d = m["delivery_metrics"]
    curve = lib.load("promise_curve").query("split == 'test'")
    c = st.columns(3)
    c[0].metric(
        "Late deliveries: Olist → model",
        f"{d['test_olist_late_pct']:.1f}% → {d['test_model_late_pct']:.1f}%",
    )
    c[1].metric(
        "Avg promise: Olist → model",
        f"{d['test_olist_avg_promise_days']:.1f} → {d['test_model_avg_promise_days']:.1f} days",
    )
    c[2].metric("Median error (days)", f"{d['test_mae_days']['lightgbm_p50']:.2f}",
                delta=f"{d['test_mae_days']['lightgbm_p50'] - d['test_mae_days']['route_history_90d']:.2f} vs route baseline",
                delta_color="inverse")  # fmt: skip
    model_pts = curve[curve["quantile"].notna()]
    olist_pt = curve[curve["policy"] == "Olist today"]
    fig = go.Figure()
    fig.add_scatter(x=model_pts["avg_promise_days"], y=model_pts["late_pct"] / 100, mode="lines+markers",
                    name="Model policies", line_color=lib.BLUE, text=model_pts["policy"],
                    hovertemplate="%{text}: %{y:.1%} late, %{x:.1f}d promise<extra></extra>")  # fmt: skip
    fig.add_scatter(x=olist_pt["avg_promise_days"], y=olist_pt["late_pct"] / 100, mode="markers",
                    name="Olist today", marker=dict(color=lib.ORANGE, size=14),
                    hovertemplate="Olist: %{y:.1%} late, %{x:.1f}d promise<extra></extra>")  # fmt: skip
    st.markdown(
        "**The model's trade-off curve beats Olist's single point: fewer late orders *and* shorter promises**"
    )
    st.plotly_chart(lib.style(fig, height=320, pct_y=True).update_layout(
        xaxis_title="Average promise (days)", yaxis_title="Late deliveries"))  # fmt: skip
    st.caption(
        "Features use only information available at purchase; seller and route track records count only orders "
        "completed *before* the purchase (leakage-tested). Seller and product attributes not on this form use typical values."
    )
