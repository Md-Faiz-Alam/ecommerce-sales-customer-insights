"""Order input form shared by the two ML pages, mapped to the models' training features."""

from __future__ import annotations

import datetime as dt

import lib
import streamlit as st

FRIENDLY = {
    "route_delivery_days": "Route: avg delivery time (all-time)",
    "route_delivery_days_90d": "Route: avg delivery time (last 90 days)",
    "route_late_rate": "Route: late rate (all-time)",
    "route_late_rate_90d": "Route: late rate (last 90 days)",
    "route_prior_orders": "Route: order volume",
    "seller_late_rate": "Seller: late rate",
    "seller_negative_rate": "Seller: negative-review rate",
    "seller_dispatch_days": "Seller: dispatch speed",
    "seller_dispatch_days_90d": "Seller: dispatch speed (90 days)",
    "seller_prior_orders": "Seller: experience (orders)",
    "estimated_delivery_days": "Olist's promise for the route",
    "max_distance_km": "Distance seller → customer",
    "dispatch_days": "Days until carrier handoff",
    "dispatched_after_limit": "Missed shipping deadline",
    "days_left_at_dispatch": "Days left before promise at handoff",
    "item_count": "Items in order",
    "product_value": "Order value",
    "freight_value": "Freight",
    "freight_ratio": "Freight / order value",
    "purchase_month": "Month of purchase",
    "purchase_dow": "Weekday of purchase",
    "customer_state": "Customer state",
    "seller_state": "Seller state",
    "main_category": "Category",
    "main_payment_type": "Payment type",
    "product_weight_g": "Product weight",
    "installments": "Installments",
    "same_state": "Same-state route",
}


def order_form(key: str) -> tuple[dict, dict]:
    """Render inputs; return (feature values, route profile)."""
    routes = lib.load("routes")
    m = lib.meta()
    cats = m["categories"]

    c1, c2, c3 = st.columns(3)
    seller_states = sorted(routes["seller_state"].unique())
    seller_state = c1.selectbox(
        "Seller state", seller_states, index=seller_states.index("SP"), key=f"{key}_ss"
    )
    options = routes[routes["seller_state"] == seller_state].sort_values("orders", ascending=False)
    cust_states = options["customer_state"].tolist()
    default_cust = cust_states.index("RJ") if "RJ" in cust_states else 0
    customer_state = c2.selectbox(
        "Customer state", cust_states, index=default_cust, key=f"{key}_cs",
        help="Only routes with 30+ historical orders are offered",
    )  # fmt: skip
    category_list = cats["main_category"]
    category = c3.selectbox(
        "Category", category_list, index=category_list.index("bed_bath_table"),
        format_func=lambda s: s.replace("_", " "), key=f"{key}_cat",
    )  # fmt: skip

    route = options[options["customer_state"] == customer_state].iloc[0].to_dict()

    c4, c5, c6, c7 = st.columns(4)
    price = c4.number_input("Item price (R$)", 5.0, 5000.0, 120.0, step=10.0, key=f"{key}_price")
    items = c5.number_input("Items", 1, 10, 1, key=f"{key}_items")
    freight = c6.number_input("Freight (R$)", 0.0, 500.0, round(float(route["freight_value"]), 2), step=1.0,
                              key=f"{key}_freight")  # fmt: skip
    weight = c7.number_input("Weight (g)", 50, 40000, 800, step=100, key=f"{key}_w")

    c8, c9, c10, c11 = st.columns(4)
    pay_list = [p for p in cats["main_payment_type"] if p not in ("unknown", "not_defined")]
    payment = c8.selectbox("Payment", pay_list, index=pay_list.index("credit_card"),
                           format_func=lambda s: s.replace("_", " "), key=f"{key}_pay")  # fmt: skip
    installments = c9.slider(
        "Installments", 1, 10, 3 if payment == "credit_card" else 1, key=f"{key}_inst"
    )
    tier = c10.selectbox("Seller track record", list(m["seller_tiers"]), index=1, key=f"{key}_tier")
    date = c11.date_input("Purchase date", dt.date(2018, 8, 15), key=f"{key}_date")

    values = dict(m["numeric_defaults"])
    values.update(m["seller_tiers"][tier])
    values.update({c: route[c] for c in lib.ROUTE_COLS})
    order_value = price * items
    values.update(
        product_value=order_value,
        freight_value=freight,
        freight_ratio=freight / order_value,
        item_count=items,
        seller_count=1,
        installments=installments,
        used_voucher=1 if payment == "voucher" else 0,
        is_repeat_customer=0,
        max_distance_km=route["max_distance_km"],
        same_state=int(seller_state == customer_state),
        estimated_delivery_days=route["estimated_delivery_days"],
        product_weight_g=weight,
        purchase_dow=date.weekday(),
        purchase_hour=14,
        purchase_month=date.month,
        customer_state=customer_state,
        seller_state=seller_state,
        main_category=category,
        main_payment_type=payment,
    )
    return values, route
