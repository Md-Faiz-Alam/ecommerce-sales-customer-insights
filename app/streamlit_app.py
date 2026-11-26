"""Olist Marketplace Insights: Streamlit entry point.

Run locally:  streamlit run app/streamlit_app.py
"""

import streamlit as st

import lib

st.set_page_config(page_title="Olist Insights", page_icon="📦", layout="wide")

pages = {
    "Analytics": [
        st.Page("pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page(
            "pages/delivery.py", title="Delivery & Satisfaction", icon=":material/local_shipping:"
        ),
        st.Page("pages/customers.py", title="Customers & Retention", icon=":material/group:"),
        st.Page("pages/sellers.py", title="Sellers", icon=":material/storefront:"),
    ],
    "Machine learning": [
        st.Page(
            "pages/promise.py",
            title="Delivery Promise Simulator",
            icon=":material/event_available:",
        ),
        st.Page("pages/risk.py", title="Review Risk Checker", icon=":material/warning:"),
        st.Page("pages/forecast.py", title="Demand Forecast", icon=":material/trending_up:"),
    ],
}
nav = st.navigation(pages)
lib.sidebar_filters()
st.sidebar.divider()
st.sidebar.caption(
    "Olist Brazilian e-commerce data, Jan 2017 – Aug 2018 · values in BRL · "
    "[Source code & analysis](https://github.com/Md-Faiz-Alam/ecommerce-sales-customer-insights)"
)
nav.run()
