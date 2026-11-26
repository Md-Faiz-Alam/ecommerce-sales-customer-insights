"""Unit tests for model evaluation logic (synthetic data, no warehouse needed)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ecom.models import forecast
from ecom.models.delivery_time import policy_stats
from ecom.models.review_risk import top_k_stats


def test_policy_stats_counts_late_against_promise():
    actual = pd.Series([5, 10, 15, 20])
    stats = policy_stats(actual, np.array([10, 10, 10, 10]))
    assert stats["late_pct"] == 50.0  # 15 and 20 arrive after a 10-day promise
    assert stats["avg_promise_days"] == 10.0


def test_top_k_stats_perfect_ranking():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 10)
    score = y + np.linspace(0, 0.1, len(y))  # positives ranked first
    s = top_k_stats(y, score, share=0.2)
    assert s["precision_top20%"] == 1.0
    assert s["recall_top20%"] == 1.0
    assert s["lift_top20%"] == pytest.approx(5.0)


def _weekly_series(weeks: int = 20) -> pd.Series:
    pattern = np.array([100, 120, 110, 105, 90, 60, 70], dtype=float)
    idx = pd.date_range("2018-01-01", periods=7 * weeks, freq="D")
    return pd.Series(np.tile(pattern, weeks), index=idx)


def test_naive_baselines_reproduce_a_stable_week():
    s = _weekly_series()
    assert np.allclose(forecast.seasonal_naive(s, 14), np.tile(s.iloc[:7], 2))
    assert np.allclose(forecast.seasonal_mean_4w(s, 7), s.iloc[:7])


def test_backtest_never_trains_on_the_future():
    s = _weekly_series()
    folds, preds = forecast.backtest(s)
    assert len(folds) == forecast.FOLDS * len(forecast.MODELS)
    # every forecast day lies inside the last FOLDS * HORIZON days
    assert preds["day"].min() == s.index[-forecast.FOLDS * forecast.HORIZON]
    # a perfectly periodic series is forecast perfectly by the seasonal naive model
    naive = folds[folds["model"] == "Seasonal naive (last week)"]
    assert naive["mae"].max() == pytest.approx(0.0)
