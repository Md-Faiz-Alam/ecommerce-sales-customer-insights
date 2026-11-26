import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import lib

st.title("Customers & Retention")

df = lib.filtered_orders()
lib.require_rows(df)
per_customer = df.groupby("customer").size()

cols = st.columns(3)
cols[0].metric("Customers", f"{len(per_customer):,}")
cols[1].metric("Ordered more than once", f"{(per_customer > 1).mean():.1%}",
               help="Within the current filters. Lifetime repeat rate: 3.1%")  # fmt: skip
cols[2].metric("Orders per customer", f"{per_customer.mean():.2f}")

st.caption(
    "Cohort and RFM views cover the whole period (they aren't affected by the sidebar filters)."
)

cohort = lib.load("cohort")
heat = cohort[cohort["months_since_first"].between(1, 12)].pivot(
    index="cohort_month", columns="months_since_first", values="retention_pct"
)
# Inside the observable range, a missing cell means 0% came back; beyond it, there's no data yet.
last = heat.index.max()
for cohort in heat.index:
    horizon = (last.year - cohort.year) * 12 + (last.month - cohort.month)
    observable = [c for c in heat.columns if c <= horizon]
    heat.loc[cohort, observable] = heat.loc[cohort, observable].fillna(0)
heat.index = heat.index.strftime("%b %Y")
labels = np.where(heat.isna(), "", heat.round(1).astype(str))
lib.takeaway("No monthly cohort ever retains more than ~1% of customers")
fig = go.Figure(
    go.Heatmap(
        z=heat.to_numpy(), x=[f"M{c}" for c in heat.columns], y=heat.index,
        colorscale=[[i / (len(lib.SEQ) - 1), c] for i, c in enumerate(lib.SEQ)],
        text=labels, texttemplate="%{text}",
        hovertemplate="Cohort %{y}, %{x}: %{z:.2f}% ordered again<extra></extra>",
        colorbar=dict(title="%"),
    )
)  # fmt: skip
fig = lib.style(fig, height=520)
st.plotly_chart(fig.update_yaxes(autorange="reversed", rangemode=None))

rfm = lib.load("rfm").sort_values("revenue_share_pct")
long = rfm.melt(
    id_vars="segment", value_vars=["customer_share_pct", "revenue_share_pct"],
    var_name="measure", value_name="share",
)  # fmt: skip
long["measure"] = long["measure"].map(
    {"customer_share_pct": "% of customers", "revenue_share_pct": "% of revenue"}
)
lib.takeaway(
    "'At-risk big spenders' are 15% of customers but 27% of revenue: the first win-back target"
)
fig = px.bar(long, x="share", y="segment", color="measure", barmode="group", orientation="h",
             color_discrete_sequence=[lib.BLUE, lib.ORANGE])  # fmt: skip
fig.update_traces(hovertemplate="%{y}: %{x:.1f}%<extra></extra>")
fig = lib.style(fig, height=420).update_layout(
    xaxis_title=None, yaxis_title=None, legend_title=None
)
st.plotly_chart(fig.update_xaxes(ticksuffix="%"))

st.dataframe(
    rfm.sort_values("revenue", ascending=False),
    hide_index=True,
    column_config={
        "revenue": st.column_config.NumberColumn("Revenue", format="R$ %.0f"),
        "avg_monetary": st.column_config.NumberColumn("Avg spend", format="R$ %.0f"),
    },
)

st.info(
    "**What to do:** win-back offer for *At-risk big spenders*; a 'second order within 30 days' flow for "
    "*New high-value* customers (the median gap to a second order is 28 days); low-cost channels only for "
    "*Hibernating*. Measure every campaign against a hold-out group."
)
