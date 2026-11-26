"""Data contracts for the clean tables (pandera) + referential-integrity checks.

The pipeline fails loudly if a contract breaks, so bad data never reaches the warehouse.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

STATES = Check.str_matches(r"^[A-Z]{2}$")
ZIP = Check.str_matches(r"^\d{5}$")
ORDER_STATUSES = [
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved",
]  # fmt: skip

SCHEMAS: dict[str, DataFrameSchema] = {
    "customers": DataFrameSchema(
        {
            "customer_id": Column(unique=True),
            "customer_unique_id": Column(),
            "customer_zip_code_prefix": Column(checks=ZIP),
            "customer_state": Column(checks=STATES),
        }
    ),
    "sellers": DataFrameSchema(
        {
            "seller_id": Column(unique=True),
            "seller_zip_code_prefix": Column(checks=ZIP),
            "seller_state": Column(checks=STATES),
        }
    ),
    "orders": DataFrameSchema(
        {
            "order_id": Column(unique=True),
            "customer_id": Column(unique=True),  # Olist issues one customer_id per order
            "order_status": Column(checks=Check.isin(ORDER_STATUSES)),
            "order_purchase_timestamp": Column("datetime64[us]"),
            "order_estimated_delivery_date": Column("datetime64[us]"),
            "order_delivered_customer_date": Column("datetime64[us]", nullable=True),
            "delivery_days": Column(float, Check.ge(0), nullable=True),
        },
        checks=[
            Check(
                lambda d: (
                    d["order_approved_at"].isna()
                    | (d["order_approved_at"] >= d["order_purchase_timestamp"])
                ),
                error="approval before purchase",
            ),
        ],
    ),
    "order_items": DataFrameSchema(
        {
            "order_id": Column(),
            "order_item_id": Column(int, Check.ge(1)),
            "price": Column(float, Check.gt(0)),
            "freight_value": Column(float, Check.ge(0)),
        },
        unique=["order_id", "order_item_id"],
    ),
    "payments": DataFrameSchema(
        {
            "payment_sequential": Column(int, Check.ge(1)),
            "payment_installments": Column(int, Check.ge(1)),
            "payment_value": Column(float, Check.ge(0)),
        },
        unique=["order_id", "payment_sequential"],
    ),
    "products": DataFrameSchema(
        {
            "product_id": Column(unique=True),
            "product_category": Column(nullable=False),
            "product_weight_g": Column(float, Check.gt(0), nullable=True),
        }
    ),
    "reviews": DataFrameSchema(
        {
            "order_id": Column(unique=True),
            "review_score": Column(int, Check.isin([1, 2, 3, 4, 5])),
        }
    ),
    "geolocation": DataFrameSchema(
        {
            "zip_code_prefix": Column(unique=True, checks=ZIP),
            "lat": Column(float, Check.between(-34, 5.5)),
            "lng": Column(float, Check.between(-74, -34)),
        }
    ),
}

# child_table.column -> parent_table.column
FOREIGN_KEYS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("payments", "order_id", "orders", "order_id"),
    ("reviews", "order_id", "orders", "order_id"),
]


class DataContractError(Exception):
    pass


def validate_all(tables: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Validate every table; raise DataContractError listing all failures."""
    results: dict[str, str] = {}
    failures: list[str] = []

    for name, schema in SCHEMAS.items():
        try:
            schema.validate(tables[name], lazy=True)
            results[f"schema:{name}"] = "passed"
        except pa.errors.SchemaErrors as exc:
            summary = exc.failure_cases[["column", "check"]].drop_duplicates().to_dict("records")
            results[f"schema:{name}"] = f"FAILED {summary}"
            failures.append(f"{name}: {summary}")

    for child, ccol, parent, pcol in FOREIGN_KEYS:
        orphans = int((~tables[child][ccol].isin(tables[parent][pcol])).sum())
        key = f"fk:{child}.{ccol} -> {parent}.{pcol}"
        results[key] = "passed" if orphans == 0 else f"FAILED ({orphans:,} orphan rows)"
        if orphans:
            failures.append(f"{key}: {orphans} orphans")

    # Coverage checks are informational (some zip prefixes are absent from Olist's geo table).
    geo_zips = tables["geolocation"]["zip_code_prefix"]
    for table, col in [
        ("customers", "customer_zip_code_prefix"),
        ("sellers", "seller_zip_code_prefix"),
    ]:
        coverage = tables[table][col].isin(geo_zips).mean()
        results[f"coverage:{table} zip -> geolocation"] = f"{coverage:.2%} matched (info)"

    if failures:
        raise DataContractError("Data contract violations:\n  " + "\n  ".join(failures))
    return results
