"""Cleaning rules, one function per table.

Principles:
- Never invent data: no 0 for an unknown weight and no fake 0-star reviews. Unknowns stay NA
  and get a flag column, so the analyst decides how to treat them per question.
- Keep rows; flag anomalies. Rows are only dropped when they are true duplicates at
  the table's grain.
- Every rule is logged with the number of rows it affected (see quality.CleaningLog).
"""

from __future__ import annotations

import pandas as pd

from ecom.config import (
    ANALYSIS_END,
    ANALYSIS_START,
    BRAZIL_LAT,
    BRAZIL_LNG,
    EXTRA_CATEGORY_TRANSLATIONS,
)
from ecom.quality import CleaningLog

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _to_ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format=TS_FORMAT, errors="raise")


def _norm_zip(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.zfill(5)


def _norm_text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower()


# --------------------------------------------------------------------------- customers
def clean_customers(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(
        customer_zip_code_prefix=_norm_zip(df["customer_zip_code_prefix"]),
        customer_city=_norm_text(df["customer_city"]),
        customer_state=df["customer_state"].astype("string").str.strip().str.upper(),
    )
    n_unique = out["customer_unique_id"].nunique()
    log.add(
        "customers",
        f"customer_id is per-order; {n_unique:,} real people (customer_unique_id). "
        "Use customer_unique_id for customer counts and retention",
        len(out) - n_unique,
        "info",
    )
    return out


# --------------------------------------------------------------------------- orders
ORDER_TS_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def clean_orders(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(**{c: _to_ts(df[c]) for c in ORDER_TS_COLS})
    out["order_status"] = _norm_text(out["order_status"])

    purchased = out["order_purchase_timestamp"]
    delivered = out["order_delivered_customer_date"]
    estimated = out["order_estimated_delivery_date"]
    status_delivered = out["order_status"].eq("delivered")

    missing_date = status_delivered & delivered.isna()
    log.add("orders", "status 'delivered' but no delivery timestamp", missing_date.sum(), "flagged")

    canceled_with_date = out["order_status"].eq("canceled") & delivered.notna()
    log.add(
        "orders",
        "status 'canceled' but has delivery timestamp",
        canceled_with_date.sum(),
        "flagged",
    )

    carrier_before_approval = out["order_delivered_carrier_date"] < out["order_approved_at"]
    log.add(
        "orders",
        "handed to carrier before payment approval (timestamp inconsistency)",
        carrier_before_approval.sum(),
        "flagged",
    )
    out["has_timestamp_anomaly"] = missing_date | canceled_with_date | carrier_before_approval

    # A completed order = delivered status AND a delivery timestamp. This is the revenue base.
    out["is_delivered"] = status_delivered & delivered.notna()

    out["purchase_date"] = purchased.dt.normalize()
    out["purchase_month"] = purchased.dt.to_period("M").dt.to_timestamp()
    out["approval_hours"] = (out["order_approved_at"] - purchased).dt.total_seconds() / 3600
    out["delivery_days"] = (delivered - purchased).dt.total_seconds() / 86400
    out["estimated_delivery_days"] = (estimated - purchased).dt.total_seconds() / 86400

    # Olist promises a calendar date, so an order is late if it arrives on a later day.
    delay = (delivered.dt.normalize() - estimated.dt.normalize()).dt.days
    out["delivery_delay_days"] = delay.astype("Int64")
    out["is_late"] = (delay > 0).astype("boolean").mask(delivered.isna())
    log.add("orders", "derived delivery_days / delivery_delay_days / is_late", len(out), "derived")

    in_window = purchased.ge(ANALYSIS_START) & purchased.lt(ANALYSIS_END)
    out["in_analysis_window"] = in_window
    log.add(
        "orders",
        f"outside analysis window {ANALYSIS_START:%Y-%m-%d} to {ANALYSIS_END:%Y-%m-%d} "
        "(sparse head/tail months)",
        (~in_window).sum(),
        "flagged",
    )

    dupes = out.duplicated("order_id")
    log.add("orders", "duplicate order_id", dupes.sum(), "dropped")
    return out.loc[~dupes].reset_index(drop=True)


# --------------------------------------------------------------------------- order items
def clean_order_items(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(
        shipping_limit_date=_to_ts(df["shipping_limit_date"]),
        item_total=df["price"] + df["freight_value"],
    )
    log.add("order_items", "derived item_total = price + freight_value", len(out), "derived")
    free_shipping = out["freight_value"].eq(0)
    log.add(
        "order_items", "zero freight (free shipping), kept as valid", free_shipping.sum(), "info"
    )
    return out


# --------------------------------------------------------------------------- payments
def clean_payments(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(payment_type=_norm_text(df["payment_type"]))

    zero_inst = out["payment_installments"].eq(0)
    out.loc[zero_inst, "payment_installments"] = 1
    log.add(
        "payments",
        "payment_installments = 0 set to 1 (a payment has >= 1 installment)",
        zero_inst.sum(),
        "fixed",
    )

    zero_value = out["payment_value"].eq(0)
    out["is_zero_value"] = zero_value
    log.add(
        "payments", "payment_value = 0 (voucher / not_defined rows)", zero_value.sum(), "flagged"
    )

    log.add(
        "payments",
        "payment_type = 'not_defined'",
        out["payment_type"].eq("not_defined").sum(),
        "flagged",
    )
    return out


# --------------------------------------------------------------------------- products
PRODUCT_RENAMES = {
    "product_name_lenght": "product_name_length",
    "product_description_lenght": "product_description_length",
}
DIM_COLS = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]


def clean_products(df: pd.DataFrame, translation: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.rename(columns=PRODUCT_RENAMES)
    log.add("products", "renamed misspelled columns (*_lenght -> *_length)", len(out), "fixed")

    mapping = dict(
        zip(
            translation["product_category_name"],
            translation["product_category_name_english"],
            strict=True,
        )
    )
    mapping |= EXTRA_CATEGORY_TRANSLATIONS

    pt = out["product_category_name"].astype("string")
    log.add("products", "missing category set to 'unknown'", pt.isna().sum(), "fixed")
    untranslated = pt.notna() & ~pt.isin(list(mapping))
    log.add(
        "products",
        "categories missing from Olist translation file, mapped manually",
        pt.isin(list(EXTRA_CATEGORY_TRANSLATIONS)).sum(),
        "fixed",
    )
    out["product_category_pt"] = pt.fillna("unknown")
    out["product_category"] = pt.map(mapping).fillna("unknown")
    out = out.drop(columns="product_category_name")
    if untranslated.any():
        raise ValueError(f"Untranslated categories: {sorted(pt[untranslated].unique())}")

    # A weight or dimension of 0 is physically impossible -> unknown, not 0.
    zero_dims = out[DIM_COLS].eq(0).any(axis=1)
    out[DIM_COLS] = out[DIM_COLS].mask(out[DIM_COLS].eq(0))
    log.add("products", "zero weight/dimension treated as missing (NA)", zero_dims.sum(), "fixed")

    out["has_missing_dims"] = out[DIM_COLS].isna().any(axis=1)
    log.add(
        "products",
        "missing weight/dimensions, kept as NA and flagged",
        out["has_missing_dims"].sum(),
        "flagged",
    )

    out["product_volume_cm3"] = (
        out["product_length_cm"] * out["product_height_cm"] * out["product_width_cm"]
    )
    int_cols = ["product_name_length", "product_description_length", "product_photos_qty"]
    out[int_cols] = out[int_cols].astype("Int64")
    return out


# --------------------------------------------------------------------------- sellers
def clean_sellers(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(
        seller_zip_code_prefix=_norm_zip(df["seller_zip_code_prefix"]),
        seller_city=_norm_text(df["seller_city"]),
        seller_state=df["seller_state"].astype("string").str.strip().str.upper(),
    )
    log.add("sellers", "normalised zip / city / state", len(out), "fixed")
    return out


# --------------------------------------------------------------------------- reviews
def clean_reviews(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.assign(
        review_creation_date=_to_ts(df["review_creation_date"]),
        review_answer_timestamp=_to_ts(df["review_answer_timestamp"]),
        review_comment_title=df["review_comment_title"].astype("string").str.strip(),
        review_comment_message=df["review_comment_message"].astype("string").str.strip(),
    )

    shared = out["review_id"].duplicated(keep=False)
    log.add(
        "reviews",
        "same review_id linked to several orders (one review for a multi-order purchase), kept",
        shared.sum(),
        "info",
    )

    # Analysis grain = one review per order: keep the most recent answer.
    out = out.sort_values(["order_id", "review_answer_timestamp", "review_creation_date"])
    multi = out.duplicated("order_id", keep="last")
    log.add("reviews", "orders with several reviews, kept latest per order", multi.sum(), "dropped")
    out = out.loc[~multi].reset_index(drop=True)

    out["has_comment"] = out["review_comment_message"].notna()
    out["is_negative"] = out["review_score"].le(2)
    log.add(
        "reviews",
        "empty comments kept as NA (no 'No Comment' placeholder)",
        (~out["has_comment"]).sum(),
        "info",
    )
    return out


# --------------------------------------------------------------------------- geolocation
def clean_geolocation(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """Collapse ~1M GPS points to one centroid per zip prefix (the join key everywhere else)."""
    g = df.assign(geolocation_zip_code_prefix=_norm_zip(df["geolocation_zip_code_prefix"]))
    inside = g["geolocation_lat"].between(*BRAZIL_LAT) & g["geolocation_lng"].between(*BRAZIL_LNG)
    log.add("geolocation", "points outside Brazil bounding box", (~inside).sum(), "dropped")
    g = g.loc[inside]

    centroids = g.groupby("geolocation_zip_code_prefix", as_index=False).agg(
        lat=("geolocation_lat", "median"),
        lng=("geolocation_lng", "median"),
    )
    state = (
        g.groupby(["geolocation_zip_code_prefix", "geolocation_state"])
        .size()
        .rename("n")
        .reset_index()
        .sort_values("n", ascending=False)
        .drop_duplicates("geolocation_zip_code_prefix")
        .drop(columns="n")
    )
    out = centroids.merge(state, on="geolocation_zip_code_prefix").rename(
        columns={"geolocation_zip_code_prefix": "zip_code_prefix", "geolocation_state": "state"}
    )
    log.add(
        "geolocation",
        f"aggregated {len(g):,} points to median centroid per zip prefix",
        len(df) - len(out),
        "derived",
    )
    return out
