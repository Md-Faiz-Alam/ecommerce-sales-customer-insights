import lib
import plotly.express as px
import streamlit as st

st.title("Olist Marketplace Insights")
st.caption(
    "Brazilian e-commerce marketplace · ~99K orders, Jan 2017 – Aug 2018 · BRL. "
    "Aug 2018 is partial (the dataset extraction ends ~21 Aug)."
)

df = lib.filtered_orders()
lib.require_rows(df)
delivered = df[df["is_delivered"]]

revenue = delivered["order_value"].sum()
cols = st.columns(6)
cols[0].metric("Revenue", lib.brl(revenue), help="Items + freight of delivered orders")
cols[1].metric("Orders", f"{len(df):,}")
cols[2].metric(
    "Customers", f"{df['customer'].nunique():,}", help="Unique people (customer_unique_id)"
)
cols[3].metric("Avg order value", lib.brl(revenue / max(len(delivered), 1)))
cols[4].metric(
    "Late deliveries", f"{delivered['is_late'].mean():.1%}", help="Arrived after the promised date"
)
cols[5].metric("Avg review", f"{df['review_score'].mean():.2f} ★")

monthly = (
    df.assign(month=df["purchase_date"].dt.to_period("M").dt.to_timestamp())
    .groupby("month")
    .agg(orders=("order_value", "size"), late=("is_late", "mean"))
    .join(
        delivered.assign(month=delivered["purchase_date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month")["order_value"]
        .sum()
        .rename("revenue")
    )
    .reset_index()
)

left, right = st.columns(2)
with left:
    lib.takeaway("Revenue more than doubled year over year, then plateaued in 2018")
    fig = px.line(monthly, x="month", y="revenue", markers=True, color_discrete_sequence=[lib.BLUE])
    fig.update_traces(hovertemplate="%{x|%b %Y}<br>R$%{y:,.0f}<extra></extra>")
    st.plotly_chart(lib.style(fig, money_y=True).update_layout(xaxis_title=None, yaxis_title=None))
with right:
    lib.takeaway("Peak months break delivery: late rate jumps from 3–6% to 12–19%")
    fig = px.line(monthly, x="month", y="late", markers=True, color_discrete_sequence=[lib.ORANGE])
    fig.update_traces(hovertemplate="%{x|%b %Y}<br>%{y:.1%} late<extra></extra>")
    st.plotly_chart(lib.style(fig, pct_y=True).update_layout(xaxis_title=None, yaxis_title=None))

left, right = st.columns(2)
with left:
    cat = (
        delivered.groupby("category", observed=True)["order_value"].sum().nlargest(10).sort_values()
    )
    lib.takeaway("Top 10 categories by revenue (no single category dominates)")
    fig = px.bar(cat, orientation="h", color_discrete_sequence=[lib.BLUE])
    fig.update_traces(hovertemplate="%{y}<br>R$%{x:,.0f}<extra></extra>")
    fig = lib.style(fig).update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig.update_xaxes(tickprefix="R$", tickformat="~s"))
with right:
    state = delivered.groupby("customer_state", observed=True)["order_value"].sum()
    share = (state / state.sum()).nlargest(10).sort_values()
    lib.takeaway(f"São Paulo alone is {share.get('SP', 0):.0%} of revenue")
    fig = px.bar(share, orientation="h", color_discrete_sequence=[lib.BLUE])
    fig.update_traces(hovertemplate="%{y}: %{x:.1%}<extra></extra>")
    fig = lib.style(fig).update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig.update_xaxes(tickformat=".0%"))

with st.expander("How these metrics are defined"):
    st.markdown(
        "- **Revenue**: item price + freight of *delivered* orders (canceled or unavailable orders are not revenue).\n"
        "- **Customers**: unique people. Olist issues a new `customer_id` per order, so the person-level ID is used.\n"
        "- **Late**: delivered on a calendar day after the promised date.\n"
        "- Category = the main (highest-priced) item's category.\n\n"
        "Full definitions: `docs/metrics.md` in the repository."
    )
