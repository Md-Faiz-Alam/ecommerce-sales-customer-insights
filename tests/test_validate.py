"""Contract tests: the validator must catch broken foreign keys and invalid values."""

from __future__ import annotations

import pandas as pd
import pytest

from ecom.validate import DataContractError, validate_all


def _valid_tables() -> dict[str, pd.DataFrame]:
    ts = pd.Timestamp("2017-05-01 10:00:00").as_unit("us")
    return {
        "customers": pd.DataFrame(
            {
                "customer_id": ["c1"],
                "customer_unique_id": ["u1"],
                "customer_zip_code_prefix": ["01037"],
                "customer_state": ["SP"],
            }
        ),
        "sellers": pd.DataFrame(
            {
                "seller_id": ["s1"],
                "seller_zip_code_prefix": ["01037"],
                "seller_state": ["SP"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": [ts],
                "order_approved_at": [ts],
                "order_estimated_delivery_date": [ts],
                "order_delivered_customer_date": [ts],
                "delivery_days": [0.0],
            }
        ),
        "order_items": pd.DataFrame(
            {
                "order_id": ["o1"],
                "order_item_id": [1],
                "product_id": ["p1"],
                "seller_id": ["s1"],
                "price": [10.0],
                "freight_value": [2.0],
            }
        ),
        "payments": pd.DataFrame(
            {
                "order_id": ["o1"],
                "payment_sequential": [1],
                "payment_installments": [1],
                "payment_value": [12.0],
            }
        ),
        "products": pd.DataFrame(
            {
                "product_id": ["p1"],
                "product_category": ["toys"],
                "product_weight_g": [100.0],
            }
        ),
        "reviews": pd.DataFrame({"order_id": ["o1"], "review_score": [5]}),
        "geolocation": pd.DataFrame({"zip_code_prefix": ["01037"], "lat": [-23.5], "lng": [-46.6]}),
    }


def test_valid_tables_pass():
    results = validate_all(_valid_tables())
    assert all(v == "passed" for k, v in results.items() if not k.startswith("coverage"))


def test_orphan_foreign_key_fails():
    tables = _valid_tables()
    tables["order_items"].loc[0, "product_id"] = "missing_product"
    with pytest.raises(DataContractError, match="order_items.product_id"):
        validate_all(tables)


def test_out_of_range_review_score_fails():
    tables = _valid_tables()
    tables["reviews"].loc[0, "review_score"] = 0
    with pytest.raises(DataContractError, match="reviews"):
        validate_all(tables)
