import lib
import numpy as np
import plotly.express as px
import streamlit as st

st.title("Seller Performance")
st.caption(
    "Scorecard for the whole period. Sellers with fewer than 30 orders are 'Low volume' (rates too noisy to rank)."
)

sc = lib.load("sellers").dropna(subset=["revenue"])
ranked = sc.sort_values("revenue", ascending=False)
top_n = int(np.ceil(len(ranked) * 0.1))
fix = sc["action_quadrant"].str.startswith("High volume, poor")

cols = st.columns(4)
cols[0].metric("Sellers with sales", f"{len(sc):,}")
cols[1].metric(
    "Revenue from top 10% of sellers",
    f"{ranked['revenue'].head(top_n).sum() / sc['revenue'].sum():.0%}",
)
cols[2].metric("'Fix first' sellers", f"{fix.sum():,}")
cols[3].metric(
    "Their share of revenue", f"{sc.loc[fix, 'revenue'].sum() / sc['revenue'].sum():.0%}"
)

rated = sc[sc["action_quadrant"] != "Low volume"].copy()
rated["group"] = np.where(rated["action_quadrant"].str.startswith("High volume, poor"),
                          "High volume, poor quality: fix first", "Other rated sellers")  # fmt: skip
lib.takeaway("164 high-volume sellers with above-median bad reviews hold a third of revenue")
fig = px.scatter(
    rated, x="revenue", y="negative_review_pct", color="group", log_x=True,
    color_discrete_map={"High volume, poor quality: fix first": lib.ORANGE, "Other rated sellers": lib.GREY},
    custom_data=["seller", "orders", "late_pct", "seller_state"],
)  # fmt: skip
fig.update_traces(
    marker=dict(size=8, line=dict(width=1, color="white")),
    hovertemplate=(
        "Seller #%{customdata[0]} (%{customdata[3]})<br>Revenue R$%{x:,.0f} · %{customdata[1]} orders"
        "<br>%{y:.1f}% negative reviews · %{customdata[2]:.1f}% late<extra></extra>"
    ),
)
fig.add_vline(x=rated["revenue"].median(), line_dash="dash", line_color=lib.GREY)
fig.add_hline(y=rated["negative_review_pct"].median(), line_dash="dash", line_color=lib.GREY)
fig = lib.style(fig, height=460).update_layout(
    xaxis_title="Seller revenue (log scale)", yaxis_title="Negative reviews (%)", legend_title=None
)
fig.update_xaxes(
    tickvals=[1e3, 3e3, 1e4, 3e4, 1e5, 3e5], tickprefix="R$", tickformat="~s", minor_showgrid=False
)
st.plotly_chart(fig)

quadrant = st.selectbox("Show sellers in quadrant", sorted(sc["action_quadrant"].unique()),
                        index=sorted(sc["action_quadrant"].unique()).index("High volume, poor quality: fix first"))  # fmt: skip
table = sc[sc["action_quadrant"] == quadrant].sort_values("revenue", ascending=False)
st.dataframe(
    table[
        [
            "seller",
            "seller_state",
            "orders",
            "revenue",
            "late_pct",
            "avg_review",
            "negative_review_pct",
        ]
    ],
    hide_index=True,
    column_config={
        "seller": st.column_config.NumberColumn("Seller #", format="%d"),
        "seller_state": "State",
        "revenue": st.column_config.ProgressColumn(
            "Revenue", format="R$ %.0f", min_value=0, max_value=float(sc["revenue"].max())
        ),
        "late_pct": st.column_config.NumberColumn("Late %", format="%.1f"),
        "negative_review_pct": st.column_config.NumberColumn("Negative %", format="%.1f"),
        "avg_review": st.column_config.NumberColumn("Avg review", format="%.2f ★"),
    },
)
st.info(
    "**What to do:** account-manage the 'fix first' sellers with dispatch SLAs and a carrier review. "
    "Their late rate is nearly double that of the 'Star' sellers, which explains much of their poor ratings."
)
