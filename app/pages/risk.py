import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import lib
from order_form import FRIENDLY, order_form

st.title("Review Risk Checker")
st.caption(
    "Scores an order when the seller hands it to the carrier: the moment ops can still act "
    "(proactive message, voucher, faster carrier) before the day-1–3 rating cliff."
)

m = lib.meta()
values, route = order_form("risk")

c1, c2 = st.columns(2)
dispatch_days = c1.slider("Days from purchase to carrier handoff", 0.0, 20.0, 2.5, 0.5)
missed = c2.toggle("Seller missed its shipping deadline", value=False)
values.update(
    dispatch_days=dispatch_days,
    dispatched_after_limit=int(missed),
    days_left_at_dispatch=route["estimated_delivery_days"] - dispatch_days,
)

X = lib.feature_frame(values, m["dispatch_features"])
model = lib.booster("review_risk")
risk = float(model.predict(X)[0])
base = m["risk_metrics"]["test_base_rate"]
percentile = float(np.searchsorted(m["risk_score_quantiles"], risk) - 1)
percentile = min(max(percentile, 0), 100)

st.divider()
cols = st.columns(3)
cols[0].metric("Chance of a 1–2★ review", f"{risk:.1%}")
cols[1].metric(
    "vs average order", f"{risk / base:.1f}×", help=f"Average negative-review rate: {base:.1%}"
)
cols[2].metric("Risk percentile", f"{percentile:.0f}th")

if percentile >= 90:
    st.error("**Flag for proactive care:** this order is in the riskiest 10%. "
             "Acting on this group reaches ~28% of all future negative reviews.")  # fmt: skip
else:
    st.success("No action needed: below the top-10% risk threshold.")

contrib = model.predict(X, pred_contrib=True)[0][:-1]  # native SHAP values; last column = bias
top = (
    pd.DataFrame({"feature": m["dispatch_features"], "impact": contrib})
    .assign(abs=lambda d: d["impact"].abs())
    .nlargest(8, "abs")
    .sort_values("impact")
)
top["label"] = top["feature"].map(FRIENDLY).fillna(top["feature"])
top["direction"] = np.where(top["impact"] > 0, "Raises risk", "Lowers risk")
lib.takeaway("Why: the biggest drivers for this order (SHAP, log-odds)")
fig = px.bar(top, x="impact", y="label", color="direction", orientation="h",
             color_discrete_map={"Raises risk": lib.ORANGE, "Lowers risk": lib.BLUE})  # fmt: skip
fig.update_traces(hovertemplate="%{y}: %{x:+.3f}<extra></extra>")
st.plotly_chart(
    lib.style(fig, height=360).update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
)

with st.expander("How good is this model? (tested on unseen months, Jun–Aug 2018)"):
    perf = pd.DataFrame(m["risk_metrics"]["models"]).T
    perf.columns = [
        "ROC-AUC",
        "PR-AUC",
        "Precision (top 10%)",
        "Recall (top 10%)",
        "Lift (top 10%)",
    ]
    st.dataframe(perf.style.format("{:.3f}"))
    st.caption(
        f"Base rate {base:.1%}. Reviews also depend on product quality and expectations, which aren't in the data, so "
        "this is a prioritisation tool. Its real effect must be measured with an A/B hold-out of flagged orders."
    )
