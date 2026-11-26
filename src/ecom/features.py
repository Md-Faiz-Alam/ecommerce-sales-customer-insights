"""Leakage-safe, order-level feature table for the ML models.

Two prediction moments, matching the two business decisions:

- PURCHASE  (payment approved): the delivery-time model predicts how long the order will take,
  so the delivery promise can be set per route instead of padded for everyone.
- DISPATCH  (seller hands the parcel to the carrier): the review-risk model flags orders likely
  to end in a 1-2 star review while there is still time to act (the "day-0 alert").

Leakage rules:
1. A feature may only use information available at its prediction moment. Delivery dates,
   delays and review fields are outcomes, never features (enforced by `assert_no_leakage`).
2. Track-record features (seller late rate, route delivery time, ...) only count outcomes
   *observed strictly before* the order's purchase timestamp (`merge_asof`, exact matches
   excluded). The order's own outcome can never leak into its own features.
3. Smoothing priors are computed from the training period only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ecom.db import query

# Time-based split (by purchase date). Never random: the models are used on future orders.
TRAIN_END = pd.Timestamp("2018-05-01")  # train:      Jan 2017 - Apr 2018
VALID_END = pd.Timestamp("2018-06-01")  # validation: May 2018 (early stopping, calibration)
#                                         test:       Jun - Aug 2018 (reported once)

SMOOTHING_K = 20  # pseudo-observations pulling sparse histories towards the prior

CATEGORICAL = ["customer_state", "seller_state", "main_category", "main_payment_type"]

PURCHASE_FEATURES = [
    # order & basket
    "product_value", "freight_value", "freight_ratio", "item_count", "seller_count",
    "installments", "used_voucher", "is_repeat_customer",
    # route & promise
    "max_distance_km", "same_state", "estimated_delivery_days", "approval_hours",
    # product
    "product_weight_g", "product_volume_cm3", "product_photos_qty", "product_description_length",
    # calendar
    "purchase_dow", "purchase_hour", "purchase_month",
    # track record (strictly prior)
    "seller_prior_orders", "seller_late_rate", "seller_negative_rate", "seller_dispatch_days",
    "seller_dispatch_days_90d", "route_prior_orders", "route_delivery_days",
    "route_delivery_days_90d", "route_late_rate", "route_late_rate_90d",
    *CATEGORICAL,
]  # fmt: skip

DISPATCH_FEATURES = [
    *PURCHASE_FEATURES,
    "dispatch_days",           # purchase -> carrier handoff
    "dispatched_after_limit",  # seller missed its shipping deadline
    "days_left_at_dispatch",   # promised date - handoff date
]  # fmt: skip

# Outcomes / post-delivery fields that must never be used as features.
FORBIDDEN = {
    "delivered_ts", "delivery_days", "delivery_cal_days", "is_late", "delivery_delay_days",
    "review_score", "review_ts", "is_negative_review",
}  # fmt: skip

BASE_SQL = """
WITH main_item AS (
    SELECT order_id,
           arg_max(seller_id, price)  AS seller_id,
           arg_max(product_id, price) AS product_id,
           min(shipping_limit_date)   AS shipping_limit_ts
    FROM marts.fact_order_items
    GROUP BY order_id
)
SELECT
    f.order_id, f.customer_state, s.state AS seller_state, mi.seller_id,
    f.order_purchase_timestamp      AS purchase_ts,
    f.order_delivered_carrier_date  AS carrier_ts,
    f.order_delivered_customer_date AS delivered_ts,
    f.order_estimated_delivery_date AS estimated_ts,
    mi.shipping_limit_ts,
    f.is_delivered, f.item_count, f.seller_count, f.main_category, f.product_value,
    f.freight_value, f.main_payment_type, f.installments, f.used_voucher, f.max_distance_km,
    f.approval_hours, f.estimated_delivery_days, f.customer_order_seq,
    p.product_weight_g, p.product_volume_cm3, p.product_photos_qty, p.product_description_length,
    -- outcomes (targets only)
    f.delivery_days, f.is_late, f.review_score, f.is_negative_review,
    r.review_answer_timestamp AS review_ts
FROM marts.fact_orders f
JOIN main_item mi USING (order_id)
JOIN marts.dim_seller s USING (seller_id)
JOIN marts.dim_product p ON p.product_id = mi.product_id
LEFT JOIN staging.reviews r USING (order_id)
WHERE f.in_analysis_window
ORDER BY f.order_id  -- stable row order -> reproducible sampling in model training
"""


def prior_history(
    orders: pd.DataFrame,
    key: str,
    event_ts: str,
    value: str,
    prior: float,
    k: float = SMOOTHING_K,
    window_days: int | None = None,
) -> pd.DataFrame:
    """Per order: count and smoothed mean of `value` over *earlier* events of the same `key`.

    An event (e.g. a delivery) counts for an order only if it happened strictly before the
    order's purchase timestamp. Mean is shrunk towards `prior`: (sum + prior*k) / (n + k).
    With `window_days`, only events in [purchase - window, purchase) count, so the feature
    adapts when operations change (cumulative sums at both edges, subtracted).
    """
    events = (
        orders.loc[orders[event_ts].notna() & orders[value].notna(), [key, event_ts, value]]
        .rename(columns={event_ts: "_event_ts"})
        .assign(_v=lambda e: e[value].astype(float))
        .sort_values("_event_ts")
    )
    events["_n"] = events.groupby(key).cumcount() + 1
    events["_sum"] = events.groupby(key)["_v"].cumsum()

    def cum_at(ts_col: str) -> pd.DataFrame:
        left = orders[["order_id", key, ts_col]].sort_values(ts_col)
        m = pd.merge_asof(
            left,
            events[[key, "_event_ts", "_n", "_sum"]],
            left_on=ts_col,
            right_on="_event_ts",
            by=key,
            allow_exact_matches=False,  # same-instant events are not "before"
            direction="backward",
        )
        return m.set_index("order_id")[["_n", "_sum"]].fillna(0)

    upper = cum_at("purchase_ts")
    if window_days is not None:
        orders = orders.assign(_lower_ts=orders["purchase_ts"] - pd.Timedelta(days=window_days))
        upper = upper - cum_at("_lower_ts").reindex(upper.index)
    n = upper["_n"]
    mean = (upper["_sum"] + prior * k) / (n + k)
    return pd.DataFrame({"n": n, "mean": mean}).reindex(orders["order_id"])


def build_features(train_end: pd.Timestamp = TRAIN_END) -> pd.DataFrame:
    """One row per order (analysis window) with features for both prediction moments + targets."""
    df = query(BASE_SQL)
    for col in ["is_late", "is_negative_review", "used_voucher"]:
        df[col] = df[col].astype("boolean")

    # Targets
    df["delivery_cal_days"] = (
        df["delivered_ts"].dt.normalize() - df["purchase_ts"].dt.normalize()
    ).dt.days

    # Purchase-time features
    df["freight_ratio"] = df["freight_value"] / df["product_value"].where(df["product_value"] > 0)
    df["same_state"] = (df["customer_state"] == df["seller_state"]).astype(int)
    df["is_repeat_customer"] = (df["customer_order_seq"] > 1).astype(int)
    df["used_voucher"] = df["used_voucher"].fillna(False).astype(int)
    df["purchase_dow"] = df["purchase_ts"].dt.dayofweek
    df["purchase_hour"] = df["purchase_ts"].dt.hour
    df["purchase_month"] = df["purchase_ts"].dt.month
    df["route"] = df["seller_state"] + ">" + df["customer_state"]

    # Dispatch-time features (known when the carrier receives the parcel)
    df["dispatch_days"] = (df["carrier_ts"] - df["purchase_ts"]).dt.total_seconds() / 86400
    df["dispatched_after_limit"] = (df["carrier_ts"] > df["shipping_limit_ts"]).astype(int)
    df["days_left_at_dispatch"] = (df["estimated_ts"] - df["carrier_ts"]).dt.total_seconds() / 86400
    df.loc[df["carrier_ts"].isna(), ["dispatched_after_limit"]] = np.nan

    # Track-record features, priors from the training period only
    train = df[df["purchase_ts"] < train_end]
    priors = {
        "late": float(train["is_late"].astype(float).mean()),
        "neg": float(train["is_negative_review"].astype(float).mean()),
        "dispatch": float(train["dispatch_days"].median()),
        "days": float(train["delivery_cal_days"].mean()),
    }
    df = df.set_index("order_id")
    # (key, event time, value, prior, feature name, rolling window in days or None for all-time)
    late, neg, disp, days = priors["late"], priors["neg"], priors["dispatch"], priors["days"]
    specs = [
        ("seller_id", "delivered_ts", "is_late", late, "seller_late_rate", None),
        ("seller_id", "review_ts", "is_negative_review", neg, "seller_negative_rate", None),
        ("seller_id", "carrier_ts", "dispatch_days", disp, "seller_dispatch_days", None),
        ("seller_id", "carrier_ts", "dispatch_days", disp, "seller_dispatch_days_90d", 90),
        ("route", "delivered_ts", "delivery_cal_days", days, "route_delivery_days", None),
        ("route", "delivered_ts", "delivery_cal_days", days, "route_delivery_days_90d", 90),
        ("route", "delivered_ts", "is_late", late, "route_late_rate", None),
        ("route", "delivered_ts", "is_late", late, "route_late_rate_90d", 90),
    ]  # fmt: skip
    base = df.reset_index()
    for key, ts, value, prior, name, window in specs:
        h = prior_history(base, key, ts, value, prior, window_days=window)
        df[name] = h["mean"].to_numpy()
        if name == "seller_late_rate":
            df["seller_prior_orders"] = h["n"].to_numpy()
        if name == "route_delivery_days":
            df["route_prior_orders"] = h["n"].to_numpy()

    for col in CATEGORICAL:
        df[col] = df[col].astype("string").fillna("unknown").astype("category")

    df["split"] = np.select(
        [df["purchase_ts"] < train_end, df["purchase_ts"] < VALID_END], ["train", "valid"], "test"
    )
    return df.reset_index()


def assert_no_leakage(features: list[str]) -> None:
    leaked = FORBIDDEN.intersection(features)
    if leaked:
        raise ValueError(f"Outcome columns used as features: {sorted(leaked)}")


assert_no_leakage(PURCHASE_FEATURES)
assert_no_leakage(DISPATCH_FEATURES)
