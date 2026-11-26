"""Leakage tests for the feature builder: an order must never see its own or future outcomes."""

from __future__ import annotations

import pandas as pd
import pytest

from ecom.features import (
    DISPATCH_FEATURES,
    FORBIDDEN,
    PURCHASE_FEATURES,
    assert_no_leakage,
    prior_history,
)


def _orders() -> pd.DataFrame:
    t = pd.Timestamp
    return pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4"],
            "seller_id": ["s1", "s1", "s1", "s2"],
            "purchase_ts": [t("2018-01-01"), t("2018-01-05"), t("2018-01-20"), t("2018-01-20")],
            # o1 delivered (late) on Jan 10; o2 delivered (on time) exactly at o3's purchase time
            "delivered_ts": [t("2018-01-10"), t("2018-01-20"), t("2018-02-01"), t("2018-01-25")],
            "is_late": [1.0, 0.0, 1.0, 1.0],
        }
    )


def test_own_and_future_outcomes_are_excluded():
    h = prior_history(_orders(), "seller_id", "delivered_ts", "is_late", prior=0.5, k=0)
    # o1: nothing delivered before Jan 1 -> no history
    assert h.loc["o1", "n"] == 0
    # o2 (Jan 5): o1 is not delivered until Jan 10 -> still no history
    assert h.loc["o2", "n"] == 0
    # o3 (Jan 20): o1 delivered Jan 10 counts; o2 delivered at exactly Jan 20 does NOT
    assert h.loc["o3", "n"] == 1
    assert h.loc["o3", "mean"] == 1.0


def test_history_is_per_key():
    h = prior_history(_orders(), "seller_id", "delivered_ts", "is_late", prior=0.5, k=0)
    assert h.loc["o4", "n"] == 0  # seller s2 has no earlier deliveries


def test_smoothing_pulls_sparse_history_to_prior():
    h = prior_history(_orders(), "seller_id", "delivered_ts", "is_late", prior=0.2, k=4)
    # o3: one late delivery, k=4 pseudo-obs at 0.2 -> (1 + 0.8) / 5
    assert h.loc["o3", "mean"] == pytest.approx(0.36)
    assert h.loc["o1", "mean"] == pytest.approx(0.2)


def test_rolling_window_drops_old_events():
    h = prior_history(
        _orders(), "seller_id", "delivered_ts", "is_late", prior=0.5, k=0, window_days=5
    )
    # o3 (Jan 20) with a 5-day window: o1's Jan 10 delivery is too old
    assert h.loc["o3", "n"] == 0


def test_feature_lists_contain_no_outcomes():
    assert not FORBIDDEN.intersection(PURCHASE_FEATURES)
    assert not FORBIDDEN.intersection(DISPATCH_FEATURES)
    with pytest.raises(ValueError, match="review_score"):
        assert_no_leakage(["price", "review_score"])
