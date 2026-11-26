"""Tests for the Power BI export formatting."""

from __future__ import annotations

import pandas as pd

from ecom.export_bi import TABLES, tidy


def test_tidy_strips_midnight_from_date_only_columns_but_keeps_timestamps():
    df = pd.DataFrame(
        {
            "Purchase Date": pd.to_datetime(["2018-01-05", "2018-01-06"]),
            "Purchase Timestamp": pd.to_datetime(["2018-01-05 16:05:07", "2018-01-06 00:00:00"]),
        }
    )
    out = tidy(df)
    assert out["Purchase Date"].tolist() == ["2018-01-05", "2018-01-06"]
    assert pd.api.types.is_datetime64_any_dtype(out["Purchase Timestamp"])


def test_tidy_rounds_money_to_cents_and_rates_to_4dp():
    df = pd.DataFrame({"Order Value": [15.620000000000001], "Late Rate": [0.0678912]})
    out = tidy(df)
    assert out.loc[0, "Order Value"] == 15.62
    assert out.loc[0, "Late Rate"] == 0.0679


def test_star_schema_tables_are_exported():
    expected = {"Orders", "Order Items", "Customers", "Products", "Sellers", "Date"}
    assert expected <= set(TABLES)
