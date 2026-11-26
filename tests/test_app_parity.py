"""Serving parity: the app's exported text models must reproduce the training predictions.

Guards against training/serving skew (column order, categorical encoding, model export).
Uses the committed app/ artefacts, so it runs in CI without the raw data.
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

APP = Path(__file__).parents[1] / "app"
pytestmark = pytest.mark.skipif(
    not (APP / "models" / "meta.json").exists(), reason="run `python -m ecom.export_app` first"
)


def _as_app_frame(rows: pd.DataFrame, features: list[str], cats: dict) -> pd.DataFrame:
    """Rebuild inputs the way app/lib.py does: plain values + training categories."""
    out = {}
    for f in features:
        if f in cats:
            out[f] = pd.Categorical(rows[f].astype(str), categories=cats[f])
        else:
            out[f] = rows[f].astype(float).to_numpy()
    return pd.DataFrame(out)[features]


@pytest.fixture(scope="module")
def artefacts():
    meta = json.loads((APP / "models" / "meta.json").read_text())
    sample = pd.read_parquet(APP / "data" / "parity_sample.parquet")
    return meta, sample


def test_delivery_model_parity(artefacts):
    meta, sample = artefacts
    rows = sample[sample["kind"] == "delivery"]
    q = meta["chosen_quantile"]
    booster = lgb.Booster(model_file=str(APP / "models" / f"delivery_p{q * 1000:.0f}.txt"))
    X = _as_app_frame(rows, meta["purchase_features"], meta["categories"])
    np.testing.assert_allclose(booster.predict(X), rows["expected"], rtol=1e-6, atol=1e-6)


def test_review_risk_model_parity(artefacts):
    meta, sample = artefacts
    rows = sample[sample["kind"] == "risk"]
    booster = lgb.Booster(model_file=str(APP / "models" / "review_risk.txt"))
    X = _as_app_frame(rows, meta["dispatch_features"], meta["categories"])
    np.testing.assert_allclose(booster.predict(X), rows["expected"], rtol=1e-6, atol=1e-6)


def test_app_bundle_is_small_enough_to_deploy():
    size_mb = sum(p.stat().st_size for p in APP.rglob("*") if p.is_file()) / 1e6
    assert size_mb < 25
