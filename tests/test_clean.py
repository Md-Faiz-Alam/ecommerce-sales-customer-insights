"""Unit tests for cleaning rules, built on tiny synthetic frames (no raw data needed in CI)."""

from __future__ import annotations

import pandas as pd
import pytest

from ecom import clean
from ecom.quality import CleaningLog


@pytest.fixture
def log() -> CleaningLog:
    return CleaningLog()


def _orders(**overrides) -> pd.DataFrame:
    base = {
        "order_id": ["o1", "o2", "o3"],
        "customer_id": ["c1", "c2", "c3"],
        "order_status": ["delivered", "delivered", "shipped"],
        "order_purchase_timestamp": ["2017-05-01 10:00:00"] * 3,
        "order_approved_at": ["2017-05-01 11:00:00"] * 3,
        "order_delivered_carrier_date": ["2017-05-02 09:00:00"] * 3,
        # o1 arrives late in the evening of the promised day -> NOT late
        # o2 arrives the day after the promised date        -> late
        "order_delivered_customer_date": ["2017-05-10 23:00:00", "2017-05-11 08:00:00", None],
        "order_estimated_delivery_date": ["2017-05-10 00:00:00"] * 3,
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestOrders:
    def test_is_late_uses_calendar_day(self, log):
        out = clean.clean_orders(_orders(), log)
        assert out["is_late"].tolist()[:2] == [False, True]
        assert out.loc[1, "delivery_delay_days"] == 1

    def test_undelivered_order_has_unknown_lateness(self, log):
        out = clean.clean_orders(_orders(), log)
        assert pd.isna(out.loc[2, "is_late"])
        assert not out.loc[2, "is_delivered"]

    def test_analysis_window_flag(self, log):
        df = _orders(
            order_purchase_timestamp=[
                "2016-10-05 10:00:00",
                "2017-05-01 10:00:00",
                "2018-09-03 10:00:00",
            ],
            order_approved_at=["2018-10-01 00:00:00"] * 3,
        )
        out = clean.clean_orders(df, log)
        assert out["in_analysis_window"].tolist() == [False, True, False]

    def test_delivered_without_date_is_flagged_not_dropped(self, log):
        df = _orders(order_delivered_customer_date=[None, "2017-05-11 08:00:00", None])
        out = clean.clean_orders(df, log)
        assert len(out) == 3
        assert out.loc[0, "has_timestamp_anomaly"]
        assert not out.loc[0, "is_delivered"]


class TestProducts:
    @pytest.fixture
    def translation(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "product_category_name": ["beleza_saude"],
                "product_category_name_english": ["health_beauty"],
            }
        )

    def _products(self, category, weight):
        return pd.DataFrame(
            {
                "product_id": ["p1"],
                "product_category_name": [category],
                "product_name_lenght": [40.0],
                "product_description_lenght": [200.0],
                "product_photos_qty": [1.0],
                "product_weight_g": [weight],
                "product_length_cm": [10.0],
                "product_height_cm": [10.0],
                "product_width_cm": [10.0],
            }
        )

    def test_translates_and_fixes_typo_columns(self, log, translation):
        out = clean.clean_products(self._products("beleza_saude", 500.0), translation, log)
        assert out.loc[0, "product_category"] == "health_beauty"
        assert "product_name_length" in out.columns
        assert "product_name_lenght" not in out.columns

    def test_manual_translation_for_missing_categories(self, log, translation):
        out = clean.clean_products(self._products("pc_gamer", 500.0), translation, log)
        assert out.loc[0, "product_category"] == "pc_gamer"

    def test_missing_category_becomes_unknown(self, log, translation):
        out = clean.clean_products(self._products(None, 500.0), translation, log)
        assert out.loc[0, "product_category"] == "unknown"

    def test_zero_weight_is_missing_not_zero(self, log, translation):
        out = clean.clean_products(self._products("beleza_saude", 0.0), translation, log)
        assert pd.isna(out.loc[0, "product_weight_g"])
        assert out.loc[0, "has_missing_dims"]

    def test_unmapped_category_raises(self, log, translation):
        with pytest.raises(ValueError, match="Untranslated"):
            clean.clean_products(self._products("nova_categoria", 1.0), translation, log)


class TestReviews:
    def test_keeps_latest_review_per_order_and_no_fake_scores(self, log):
        df = pd.DataFrame(
            {
                "review_id": ["r1", "r2", "r3"],
                "order_id": ["o1", "o1", "o2"],
                "review_score": [1, 5, 3],
                "review_comment_title": [None, None, None],
                "review_comment_message": ["ruim", None, None],
                "review_creation_date": [
                    "2017-01-01 00:00:00",
                    "2017-01-05 00:00:00",
                    "2017-01-02 00:00:00",
                ],
                "review_answer_timestamp": [
                    "2017-01-02 00:00:00",
                    "2017-01-06 00:00:00",
                    "2017-01-03 00:00:00",
                ],
            }
        )
        out = clean.clean_reviews(df, log).set_index("order_id")
        assert len(out) == 2
        assert out.loc["o1", "review_score"] == 5
        assert out["review_score"].between(1, 5).all()
        assert pd.isna(out.loc["o2", "review_comment_message"])


def test_payment_zero_installments_fixed(log):
    df = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "payment_sequential": [1, 1],
            "payment_type": ["credit_card", "voucher"],
            "payment_installments": [0, 1],
            "payment_value": [10.0, 0.0],
        }
    )
    out = clean.clean_payments(df, log)
    assert out["payment_installments"].tolist() == [1, 1]
    assert out["is_zero_value"].tolist() == [False, True]


def test_geolocation_drops_outliers_and_pads_zip(log):
    df = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": ["1037", "1037", "1037"],
            "geolocation_lat": [-23.5, -23.7, 45.0],  # last point is in Europe
            "geolocation_lng": [-46.6, -46.8, 2.0],
            "geolocation_city": ["sao paulo"] * 3,
            "geolocation_state": ["SP"] * 3,
        }
    )
    out = clean.clean_geolocation(df, log)
    assert out["zip_code_prefix"].tolist() == ["01037"]
    assert out.loc[0, "lat"] == pytest.approx(-23.6)
