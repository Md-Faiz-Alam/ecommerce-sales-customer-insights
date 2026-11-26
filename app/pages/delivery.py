import lib
import plotly.express as px
import streamlit as st

st.title("Delivery & Satisfaction")
st.caption(
    "The flagship finding: customers judge delivery against the promise, not absolute speed."
)

df = lib.filtered_orders()
lib.require_rows(df)
d = df[df["is_delivered"]]
reviewed = d.dropna(subset=["review_score"])

cols = st.columns(5)
cols[0].metric("Late deliveries", f"{d['is_late'].mean():.1%}")
cols[1].metric("Avg delivery", f"{d['delivery_days'].mean():.1f} days")
cols[2].metric("Avg promise", f"{d['promised_days'].mean():.1f} days")
cols[3].metric("Promise buffer", f"{(d['promised_days'] - d['delivery_days']).mean():.1f} days")
cols[4].metric("Negative reviews (delivered)", f"{reviewed['is_negative_review'].mean():.1%}")

buckets = (
    reviewed.assign(timing=lib.timing_bucket(reviewed["delay_days"]))
    .groupby("timing", observed=False)["is_negative_review"]
    .agg(rate="mean", orders="size")
    .reset_index()
)
buckets["late"] = buckets["timing"].astype(str).str.contains("late")
lib.takeaway("One day late doubles bad reviews; a week late, two in three customers leave 1–2★")
fig = px.bar(
    buckets, x="timing", y="rate", color="late", text="rate",
    color_discrete_map={False: lib.BLUE, True: lib.ORANGE}, custom_data=["orders"],
)  # fmt: skip
fig.update_traces(
    texttemplate="%{y:.0%}", textposition="outside",
    hovertemplate="%{x}<br>%{y:.1%} negative · %{customdata[0]:,} orders<extra></extra>",
)  # fmt: skip
fig = lib.style(fig, height=380, pct_y=True).update_layout(
    showlegend=False, xaxis_title="Delivery vs promised date", yaxis_title="Negative reviews"
)
st.plotly_chart(fig)

left, right = st.columns(2)
with left:
    curve = (
        reviewed[reviewed["delay_days"].between(-10, 15)]
        .groupby("delay_days")["is_negative_review"]
        .mean()
        .reset_index()
    )
    lib.takeaway("The cliff starts right after the promised day")
    fig = px.line(curve, x="delay_days", y="is_negative_review", markers=True,
                  color_discrete_sequence=[lib.BLUE])  # fmt: skip
    fig.add_vline(x=0.5, line_dash="dash", line_color=lib.GREY)
    fig.update_traces(hovertemplate="%{x:+d} days<br>%{y:.1%} negative<extra></extra>")
    st.plotly_chart(lib.style(fig, pct_y=True).update_layout(
        xaxis_title="Days after (+) / before (−) promise", yaxis_title=None))  # fmt: skip
with right:
    by_state = d.groupby("customer_state", observed=True).agg(
        late=("is_late", "mean"), n=("is_late", "size")
    )
    by_state = by_state[by_state["n"] >= 200].sort_values("late")
    avg = d["is_late"].mean()
    by_state["above"] = by_state["late"] > avg
    lib.takeaway("The North-East is late most often (states with 200+ orders)")
    fig = px.bar(by_state.reset_index(), x="late", y="customer_state", orientation="h", color="above",
                 color_discrete_map={False: lib.BLUE, True: lib.ORANGE})  # fmt: skip
    fig.add_vline(x=avg, line_dash="dash", line_color=lib.GREY, annotation_text=f"avg {avg:.1%}")
    fig.update_traces(hovertemplate="%{y}: %{x:.1%} late<extra></extra>")
    fig = lib.style(fig, height=520).update_layout(
        showlegend=False, xaxis_title=None, yaxis_title=None
    )
    st.plotly_chart(fig.update_xaxes(tickformat=".0%"))

st.info(
    "**What to do:** set promises per route from a delivery-time model (see *Delivery Promise Simulator*) and "
    "flag at-risk orders at carrier handoff before the day-1–3 cliff (see *Review Risk Checker*). "
    "Statistical tests (Mann-Whitney U, relative risk 6.7× with 95% CI, state-adjusted Mantel-Haenszel) are in notebook 04."
)
