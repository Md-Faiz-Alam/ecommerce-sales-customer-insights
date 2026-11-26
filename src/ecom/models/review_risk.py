"""Negative-review risk model -> "day-0 alert" at carrier handoff.

Business problem (notebook 04): ratings collapse within 1-3 days of a missed promise. Scoring
each order when the seller hands it to the carrier leaves days to act (a proactive message, a
voucher, faster shipping) before the customer is disappointed.

Target: review_score <= 2. Evaluated on a later time period (Jun-Aug 2018). Models compared:
- logistic regression baseline (dispatch features, numeric only)
- LightGBM with purchase-time features only (what we would know at checkout)
- LightGBM with dispatch-time features (the deployed model)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ecom.features import CATEGORICAL, DISPATCH_FEATURES, PURCHASE_FEATURES

PARAMS = dict(
    n_estimators=3000,
    learning_rate=0.03,
    num_leaves=31,
    min_child_samples=100,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=42,
    deterministic=True,
    force_row_wise=True,
    verbose=-1,
)
TOP_SHARE = 0.10  # share of orders the ops team can act on


@dataclass
class ReviewRiskModel:
    model: lgb.LGBMClassifier
    features: list[str] = field(default_factory=lambda: list(DISPATCH_FEATURES))

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X[self.features])[:, 1]


def modelling_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Delivered orders with a review and a carrier handoff (i.e. scoreable at dispatch)."""
    mask = (
        features["is_delivered"] & features["review_score"].notna() & features["carrier_ts"].notna()
    )
    df = features[mask].copy()
    df["target"] = df["is_negative_review"].astype(int)
    return df


def top_k_stats(y: np.ndarray, score: np.ndarray, share: float = TOP_SHARE) -> dict[str, float]:
    """Precision / recall / lift when acting on the top `share` riskiest orders."""
    k = max(1, int(len(score) * share))
    top = np.argsort(-score)[:k]
    precision = y[top].mean()
    return {
        f"precision_top{share:.0%}": float(precision),
        f"recall_top{share:.0%}": float(y[top].sum() / y.sum()),
        f"lift_top{share:.0%}": float(precision / y.mean()),
    }


def evaluate(y: np.ndarray, score: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y, score)),
        "pr_auc": float(average_precision_score(y, score)),
        **top_k_stats(y, score),
    }


def _fit_lgbm(tr: pd.DataFrame, va: pd.DataFrame, features: list[str]) -> lgb.LGBMClassifier:
    m = lgb.LGBMClassifier(objective="binary", **PARAMS)
    m.fit(
        tr[features],
        tr["target"],
        eval_X=(va[features],),
        eval_y=(va["target"],),
        eval_metric="average_precision",
        callbacks=[lgb.early_stopping(150, verbose=False)],
    )
    return m


def train(features: pd.DataFrame) -> tuple[ReviewRiskModel, dict, pd.DataFrame]:
    df = modelling_frame(features)
    tr, va, te = (df[df["split"] == s] for s in ("train", "valid", "test"))
    y_te = te["target"].to_numpy()

    numeric = [f for f in DISPATCH_FEATURES if f not in CATEGORICAL]
    logit = make_pipeline(
        SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000)
    )
    logit.fit(tr[numeric], tr["target"])

    lgbm_purchase = _fit_lgbm(tr, va, PURCHASE_FEATURES)
    lgbm_dispatch = _fit_lgbm(tr, va, DISPATCH_FEATURES)

    scores = {
        "Logistic regression (dispatch)": logit.predict_proba(te[numeric])[:, 1],
        "LightGBM (purchase-time)": lgbm_purchase.predict_proba(te[PURCHASE_FEATURES])[:, 1],
        "LightGBM (dispatch-time)": lgbm_dispatch.predict_proba(te[DISPATCH_FEATURES])[:, 1],
    }
    comparison = pd.DataFrame({name: evaluate(y_te, s) for name, s in scores.items()}).T
    metrics = {
        "rows": {"train": len(tr), "valid": len(va), "test": len(te)},
        "test_base_rate": float(y_te.mean()),
        "models": comparison.to_dict(orient="index"),
        "best_iteration": int(lgbm_dispatch.best_iteration_),
    }
    scored = te[["order_id", "target"]].assign(risk=scores["LightGBM (dispatch-time)"])
    return ReviewRiskModel(lgbm_dispatch), metrics, scored
