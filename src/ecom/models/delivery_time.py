"""Delivery-time model -> route-level delivery promises.

Business problem (notebook 04): Olist promises ~24 days for a ~12-day delivery, yet early
delivery earns no rating credit and a uniform promise cut backfires. This model predicts
delivery-time *quantiles* per order at purchase time. A promise = ceil(predicted quantile).
Higher quantile = safer promise, longer wait. The quantile is chosen on the validation month so
the late rate is no worse than Olist's current promise, then evaluated once on the test period.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from ecom.features import PURCHASE_FEATURES

QUANTILES = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.975]

PARAMS = dict(
    n_estimators=3000,
    learning_rate=0.05,
    num_leaves=63,
    min_child_samples=50,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    random_state=42,
    deterministic=True,
    force_row_wise=True,
    verbose=-1,
)


@dataclass
class DeliveryTimeModel:
    models: dict[float, lgb.LGBMRegressor] = field(default_factory=dict)
    chosen_quantile: float | None = None
    features: list[str] = field(default_factory=lambda: list(PURCHASE_FEATURES))

    def predict_days(self, X: pd.DataFrame, q: float | None = None) -> np.ndarray:
        q = q if q is not None else self.chosen_quantile
        return self.models[q].predict(X[self.features])

    def promise_days(self, X: pd.DataFrame, q: float | None = None) -> np.ndarray:
        """Promise in whole calendar days (at least 1)."""
        return np.maximum(np.ceil(self.predict_days(X, q)), 1).astype(int)


def modelling_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Delivered orders with a valid delivery time; adds Olist's own promise for comparison."""
    df = features[features["is_delivered"] & features["delivery_cal_days"].ge(0)].copy()
    df["olist_promise_days"] = (
        df["estimated_ts"].dt.normalize() - df["purchase_ts"].dt.normalize()
    ).dt.days
    return df


def policy_stats(actual: pd.Series, promise: np.ndarray | pd.Series) -> dict[str, float]:
    promise = np.asarray(promise)
    return {
        "late_pct": float(np.mean(actual.to_numpy() > promise) * 100),
        "avg_promise_days": float(np.mean(promise)),
    }


def train(features: pd.DataFrame) -> tuple[DeliveryTimeModel, dict, pd.DataFrame]:
    df = modelling_frame(features)
    tr, va, te = (df[df["split"] == s] for s in ("train", "valid", "test"))
    target = "delivery_cal_days"
    model = DeliveryTimeModel()

    for q in QUANTILES:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, **PARAMS)
        m.fit(
            tr[model.features],
            tr[target],
            eval_X=(va[model.features],),
            eval_y=(va[target],),
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        model.models[q] = m

    # Trade-off curve: each quantile is a candidate promise policy.
    rows = []
    for split_name, part in (("valid", va), ("test", te)):
        olist = policy_stats(part[target], part["olist_promise_days"])
        rows.append({"split": split_name, "policy": "Olist today", "quantile": np.nan, **olist})
        for q in QUANTILES:
            stats = policy_stats(part[target], model.promise_days(part, q))
            rows.append(
                {"split": split_name, "policy": f"Model P{q * 100:g}", "quantile": q, **stats}
            )
    curve = pd.DataFrame(rows)

    # Choose the shortest promise whose validation late rate is no worse than Olist's.
    v = curve[curve["split"] == "valid"]
    olist_late_valid = v.loc[v["policy"] == "Olist today", "late_pct"].iloc[0]
    ok = v[(v["quantile"].notna()) & (v["late_pct"] <= olist_late_valid)]
    model.chosen_quantile = float(ok["quantile"].min() if len(ok) else max(QUANTILES))

    t = curve[curve["split"] == "test"]
    chosen = t[t["quantile"] == model.chosen_quantile].iloc[0]
    olist_t = t[t["policy"] == "Olist today"].iloc[0]

    # Point accuracy of the median model vs simple baselines (test).
    median_pred = model.predict_days(te, 0.5)
    mae = lambda pred: float(np.mean(np.abs(te[target].to_numpy() - pred)))  # noqa: E731
    metrics = {
        "rows": {"train": len(tr), "valid": len(va), "test": len(te)},
        "chosen_quantile": model.chosen_quantile,
        "test_olist_late_pct": olist_t["late_pct"],
        "test_olist_avg_promise_days": olist_t["avg_promise_days"],
        "test_model_late_pct": chosen["late_pct"],
        "test_model_avg_promise_days": chosen["avg_promise_days"],
        "test_promise_days_saved": olist_t["avg_promise_days"] - chosen["avg_promise_days"],
        "test_mae_days": {
            "lightgbm_p50": mae(median_pred),
            "route_history_90d": mae(te["route_delivery_days_90d"].to_numpy()),
            "train_median": mae(np.full(len(te), tr[target].median())),
        },
        "test_actual_avg_days": float(te[target].mean()),
    }
    return model, metrics, curve
