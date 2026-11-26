"""Export everything the Streamlit app needs into app/ (small enough to commit and deploy).

Run:  python -m ecom.export_app

app/data/    order-level facts (IDs replaced by integer codes), cohort, RFM, seller scorecard,
             forecast, route profiles, and sample rows for the serving-parity test
app/models/  LightGBM models as portable text files + meta.json (features, categories, metrics)

The app never imports this package: it only reads these files, so it deploys anywhere.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from ecom.config import ROOT
from ecom.db import query
from ecom.features import CATEGORICAL, DISPATCH_FEATURES, PURCHASE_FEATURES, build_features
from ecom.models import delivery_time, forecast, review_risk

log = logging.getLogger("ecom.export_app")
APP_DIR = ROOT / "app"
DATA_OUT = APP_DIR / "data"
MODEL_OUT = APP_DIR / "models"

APP_QUANTILES = [0.5, 0.75, 0.85, 0.9, 0.925, 0.95, 0.975]
SELLER_COLS = [
    "seller_prior_orders", "seller_late_rate", "seller_negative_rate",
    "seller_dispatch_days", "seller_dispatch_days_90d",
]  # fmt: skip
ROUTE_COLS = [
    "route_prior_orders", "route_delivery_days", "route_delivery_days_90d",
    "route_late_rate", "route_late_rate_90d",
]  # fmt: skip


def _orders() -> pd.DataFrame:
    df = query(
        """
        WITH main_seller AS (
            SELECT order_id, arg_max(seller_id, price) AS seller_id
            FROM marts.fact_order_items GROUP BY 1
        )
        SELECT f.purchase_date, f.customer_unique_id, ms.seller_id, f.customer_state,
               s.state AS seller_state, replace(f.main_category, '_', ' ') AS category,
               f.order_status, f.is_delivered, f.is_late, f.order_value, f.freight_value,
               f.delivery_days, f.estimated_delivery_days AS promised_days,
               f.delivery_delay_days AS delay_days, f.review_score, f.is_negative_review
        FROM marts.fact_orders f
        LEFT JOIN main_seller ms USING (order_id)
        LEFT JOIN marts.dim_seller s USING (seller_id)
        WHERE f.in_analysis_window
        ORDER BY f.purchase_date, f.order_id
        """
    )
    # Integer codes instead of 32-char hashes: same analytics, ~10x smaller file.
    df["customer"] = pd.factorize(df.pop("customer_unique_id"))[0].astype("int32")
    df["seller"] = pd.factorize(df.pop("seller_id"))[0].astype("int32")
    for col in ["customer_state", "seller_state", "category", "order_status"]:
        df[col] = df[col].astype("category")
    for col in ["order_value", "freight_value", "delivery_days", "promised_days"]:
        df[col] = df[col].astype("float32").round(2)
    return df


def _route_profiles(feats: pd.DataFrame) -> pd.DataFrame:
    """Latest track record + typical order attributes per seller-state -> customer-state route."""
    f = feats.sort_values("purchase_ts")
    latest = f.groupby("route")[ROUTE_COLS].last()
    typical = f.groupby("route").agg(
        orders=("order_id", "size"),
        seller_state=("seller_state", "first"),
        customer_state=("customer_state", "first"),
        max_distance_km=("max_distance_km", "median"),
        estimated_delivery_days=("estimated_delivery_days", "median"),
        actual_days_median=("delivery_cal_days", "median"),
        freight_value=("freight_value", "median"),
    )
    out = typical.join(latest)
    out = out[out["orders"] >= 30]  # enough history for a meaningful profile
    for c in ["seller_state", "customer_state"]:
        out[c] = out[c].astype(str)
    return out.reset_index()


def _feature_defaults(feats: pd.DataFrame) -> dict:
    recent = feats[feats["split"] == "test"]
    num = [c for c in DISPATCH_FEATURES if c not in CATEGORICAL]
    defaults = {c: float(recent[c].median()) for c in num}
    seller_tiers = {
        tier: {c: float(recent[c].quantile(q)) for c in SELLER_COLS}
        for tier, q in (
            ("Reliable (top 10%)", 0.1),
            ("Typical", 0.5),
            ("Unreliable (bottom 10%)", 0.9),
        )
    }
    seller_tiers["Reliable (top 10%)"]["seller_prior_orders"] = float(
        recent["seller_prior_orders"].quantile(0.9)
    )
    return {"numeric_defaults": defaults, "seller_tiers": seller_tiers}


def export() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    MODEL_OUT.mkdir(parents=True, exist_ok=True)

    log.info("Order-level data and analysis tables")
    _orders().to_parquet(DATA_OUT / "orders.parquet", index=False, compression="zstd")
    query("SELECT * FROM analysis.cohort_retention").to_parquet(DATA_OUT / "cohort.parquet")
    query("SELECT * FROM analysis.rfm_segment_summary").to_parquet(DATA_OUT / "rfm.parquet")
    sc = query("SELECT * EXCLUDE (seller_city) FROM analysis.seller_scorecard")
    sc["seller"] = pd.factorize(sc.pop("seller_id"))[0].astype("int32")
    sc.to_parquet(DATA_OUT / "sellers.parquet", index=False)

    log.info("Forecast")
    series = forecast.daily_orders()
    folds, preds = forecast.backtest(series)
    fut = forecast.forecast_future(series).rename_axis("day").reset_index()
    pd.DataFrame({"day": series.index, "orders": series.to_numpy()}).to_parquet(
        DATA_OUT / "daily_orders.parquet", index=False
    )
    fut.to_parquet(DATA_OUT / "forecast.parquet", index=False)
    preds.to_parquet(DATA_OUT / "backtest.parquet", index=False)
    summary = forecast.summarise(folds, preds, series).reset_index()

    log.info("Training models for the app")
    feats = build_features()
    dt_model, dt_metrics, curve = delivery_time.train(feats)
    rr_model, rr_metrics, scored = review_risk.train(feats)

    for q in APP_QUANTILES:
        dt_model.models[q].booster_.save_model(str(MODEL_OUT / f"delivery_p{q * 1000:.0f}.txt"))
    rr_model.model.booster_.save_model(str(MODEL_OUT / "review_risk.txt"))
    _route_profiles(feats).to_parquet(DATA_OUT / "routes.parquet", index=False)
    curve.to_parquet(DATA_OUT / "promise_curve.parquet", index=False)

    # Sample rows + reference predictions for the serving-parity test.
    te_d = delivery_time.modelling_frame(feats).query("split == 'test'").sample(50, random_state=1)
    te_r = review_risk.modelling_frame(feats).query("split == 'test'").sample(50, random_state=1)
    sample = pd.concat(
        [
            te_d[DISPATCH_FEATURES].assign(
                kind="delivery", expected=dt_model.predict_days(te_d, dt_model.chosen_quantile)
            ),
            te_r[DISPATCH_FEATURES].assign(kind="risk", expected=rr_model.predict_risk(te_r)),
        ],
        ignore_index=True,
    )
    sample.to_parquet(DATA_OUT / "parity_sample.parquet", index=False)

    risk_q = np.quantile(scored["risk"], np.linspace(0, 1, 101)).tolist()
    meta = {
        "purchase_features": PURCHASE_FEATURES,
        "dispatch_features": DISPATCH_FEATURES,
        "categories": {c: [str(v) for v in feats[c].cat.categories] for c in CATEGORICAL},
        "quantiles": APP_QUANTILES,
        "chosen_quantile": dt_model.chosen_quantile,
        "delivery_metrics": dt_metrics,
        "risk_metrics": rr_metrics,
        "risk_score_quantiles": risk_q,
        "forecast_summary": summary.to_dict(orient="records"),
        **_feature_defaults(feats),
    }
    (MODEL_OUT / "meta.json").write_text(json.dumps(meta, indent=1, default=float) + "\n")
    size = sum(p.stat().st_size for p in APP_DIR.rglob("*") if p.is_file()) / 1e6
    log.info("App files -> %s (%.1f MB)", APP_DIR, size)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")  # fmt: skip
    export()


if __name__ == "__main__":
    main()
