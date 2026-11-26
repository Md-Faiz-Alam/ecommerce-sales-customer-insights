"""End-to-end pipeline test on a synthetic, Olist-shaped dataset (no real data needed).

Runs the real code path: raw CSVs -> load -> clean -> data contracts -> Parquet -> DuckDB ->
every SQL model in sql/ -> all SQL data tests -> data-quality report.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from ecom.config import RAW_FILES, SQL_DIR
from ecom.ingest import load_all
from ecom.pipeline import clean_all
from ecom.quality import CleaningLog, write_report
from ecom.validate import validate_all
from ecom.warehouse import build_warehouse, write_parquet

TS = "%Y-%m-%d %H:%M:%S"
STATES = {
    "SP": ("01037", -23.55, -46.63),
    "RJ": ("20040", -22.90, -43.17),
    "MG": ("30110", -19.92, -43.94),
}
CATEGORIES = {"beleza_saude": "health_beauty", "esporte_lazer": "sports_leisure", "pc_gamer": None}


def make_raw(raw_dir: Path, n_orders: int = 300, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    states = list(STATES)

    sellers = pd.DataFrame({
        "seller_id": [f"s{i}" for i in range(10)],
        "seller_zip_code_prefix": [int(STATES[states[i % 3]][0]) for i in range(10)],
        "seller_city": "cidade",
        "seller_state": [states[i % 3] for i in range(10)],
    })  # fmt: skip
    products = pd.DataFrame({
        "product_id": [f"p{i}" for i in range(20)],
        "product_category_name": [list(CATEGORIES)[i % 3] if i != 19 else None for i in range(20)],
        "product_name_lenght": 40.0, "product_description_lenght": 300.0, "product_photos_qty": 2.0,
        "product_weight_g": [0.0 if i == 5 else 500.0 + i for i in range(20)],  # one fake zero
        "product_length_cm": 20.0, "product_height_cm": 10.0, "product_width_cm": 15.0,
    })  # fmt: skip
    translation = pd.DataFrame({
        "product_category_name": ["beleza_saude", "esporte_lazer"],
        "product_category_name_english": ["health_beauty", "sports_leisure"],
    })  # fmt: skip

    unique_ids = [f"u{rng.integers(0, 200)}" for _ in range(n_orders)]  # some people repeat
    purchase = pd.Timestamp("2017-01-02") + pd.to_timedelta(
        rng.integers(0, 590, n_orders), unit="D"
    )
    purchase = purchase + pd.to_timedelta(rng.integers(8, 20, n_orders), unit="h")
    cust_state = [states[i] for i in rng.integers(0, 3, n_orders)]
    customers = pd.DataFrame({
        "customer_id": [f"c{i}" for i in range(n_orders)],
        "customer_unique_id": unique_ids,
        "customer_zip_code_prefix": [int(STATES[s][0]) for s in cust_state],
        "customer_city": "cidade", "customer_state": cust_state,
    })  # fmt: skip

    transit = rng.integers(2, 30, n_orders)
    promise = rng.integers(10, 30, n_orders)
    status = np.where(rng.random(n_orders) < 0.95, "delivered", "canceled")
    delivered = purchase + pd.to_timedelta(transit, unit="D")
    delivered_str = np.where(status == "delivered", delivered.strftime(TS), None)
    estimated = purchase.normalize() + pd.to_timedelta(promise, unit="D")
    orders = pd.DataFrame({
        "order_id": [f"o{i}" for i in range(n_orders)],
        "customer_id": customers["customer_id"],
        "order_status": status,
        "order_purchase_timestamp": purchase.strftime(TS),
        "order_approved_at": (purchase + pd.Timedelta(hours=1)).strftime(TS),
        "order_delivered_carrier_date": (purchase + pd.Timedelta(days=1)).strftime(TS),
        "order_delivered_customer_date": delivered_str,
        "order_estimated_delivery_date": estimated.strftime(TS),
    })  # fmt: skip

    n_items = rng.integers(1, 3, n_orders)
    items = pd.DataFrame([
        {
            "order_id": f"o{i}", "order_item_id": k + 1,
            "product_id": f"p{rng.integers(0, 20)}", "seller_id": f"s{rng.integers(0, 10)}",
            "shipping_limit_date": (purchase[i] + pd.Timedelta(days=3)).strftime(TS),
            "price": float(rng.integers(20, 300)), "freight_value": float(rng.integers(5, 40)),
        }
        for i in range(n_orders) for k in range(n_items[i])
    ])  # fmt: skip
    totals = items.groupby("order_id").apply(
        lambda g: (g["price"] + g["freight_value"]).sum(), include_groups=False
    )
    payments = pd.DataFrame({
        "order_id": totals.index, "payment_sequential": 1, "payment_type": "credit_card",
        "payment_installments": 1, "payment_value": totals.to_numpy(),
    })  # fmt: skip

    reviews = pd.DataFrame({
        "review_id": [f"r{i}" for i in range(n_orders)],
        "order_id": orders["order_id"],
        "review_score": np.where(transit > promise, 1, 5),
        "review_comment_title": None, "review_comment_message": None,
        "review_creation_date": delivered.strftime(TS),
        "review_answer_timestamp": (delivered + pd.Timedelta(days=1)).strftime(TS),
    })  # fmt: skip
    # A duplicate review for one order (the pipeline must keep only the latest).
    dup = reviews.iloc[[0]].assign(review_id="r_dup", review_score=3)
    dup["review_answer_timestamp"] = (pd.Timestamp(reviews.loc[0, "review_answer_timestamp"])
                                      + pd.Timedelta(days=2)).strftime(TS)  # fmt: skip
    reviews = pd.concat([reviews, dup], ignore_index=True)

    points = [(int(z), lat + d, lng + d, s) for s, (z, lat, lng) in STATES.items()
              for d in (-0.01, 0.0, 0.01)]  # fmt: skip
    points.append((1037, 45.0, 2.0, "SP"))  # GPS outlier in Europe
    geo = pd.DataFrame(points, columns=[
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_state",
    ]).assign(geolocation_city="cidade")  # fmt: skip

    frames = {
        "customers": customers, "orders": orders, "order_items": items, "payments": payments,
        "reviews": reviews, "products": products, "sellers": sellers, "geolocation": geo,
        "category_translation": translation,
    }  # fmt: skip
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        df.to_csv(raw_dir / RAW_FILES[name], index=False)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    make_raw(root / "raw")
    raw = load_all(root / "raw")
    audit = CleaningLog()
    tables = clean_all(raw, audit)
    validation = validate_all(tables)
    write_parquet(tables, root / "processed")
    result = build_warehouse(root / "processed", root / "warehouse.duckdb", SQL_DIR)
    return root, raw, tables, audit, validation, result


def test_contracts_and_sql_tests_pass(built):
    _, _, _, _, validation, result = built
    assert all(v == "passed" for k, v in validation.items() if not k.startswith("coverage"))
    assert len(result.tests) >= 8
    assert all(v == "passed" for v in result.tests.values())


def test_marts_and_views_are_built(built):
    root, raw, *_, result = built
    assert result.row_counts["marts.fact_orders"] == len(raw["orders"])
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        views = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'analysis'"
        ).fetchall()}  # fmt: skip
        assert {"kpi_monthly", "cohort_retention", "customer_rfm", "category_pareto",
                "seller_scorecard", "delivery_vs_review"} <= views  # fmt: skip
        late_reviews = con.execute(
            "SELECT avg(review_score) FROM marts.fact_orders WHERE is_late"
        ).fetchone()[0]
        assert late_reviews == pytest.approx(1.0)  # fixture: late orders score 1


def test_cleaning_rules_applied(built):
    _, _, tables, *_ = built
    products = tables["products"]
    assert products.loc[products["product_id"] == "p5", "product_weight_g"].isna().all()
    assert set(products["product_category"]) == {
        "health_beauty",
        "sports_leisure",
        "pc_gamer",
        "unknown",
    }
    assert tables["reviews"]["order_id"].is_unique
    assert tables["reviews"].set_index("order_id").loc["o0", "review_score"] == 3  # latest kept
    assert len(tables["geolocation"]) == 3  # outlier dropped, one centroid per zip


def test_quality_report_is_written(built, tmp_path):
    _, raw, tables, audit, validation, result = built
    path = tmp_path / "report.md"
    counts = {k: (len(raw[k]), len(v)) for k, v in tables.items()}
    write_report(path, audit, counts, validation | result.tests)
    text = path.read_text(encoding="utf-8")
    assert "# Data Quality Report" in text and "sql:test_revenue_reconciles" in text


@pytest.fixture
def fixture_warehouse(built, monkeypatch):
    """Point ecom.db (used by features and models) at the synthetic warehouse."""
    import ecom.db as db

    monkeypatch.setattr(db, "WAREHOUSE_PATH", built[0] / "warehouse.duckdb")
    db._connection.cache_clear()
    yield
    db._connection.cache_clear()


def test_features_and_models_train_on_fixture(fixture_warehouse):
    from ecom.features import DISPATCH_FEATURES, build_features
    from ecom.models import delivery_time, forecast, review_risk

    feats = build_features()
    assert set(feats["split"]) == {"train", "valid", "test"}
    assert set(DISPATCH_FEATURES) <= set(feats.columns)

    dt_model, dt_metrics, curve = delivery_time.train(feats)
    assert dt_model.chosen_quantile in delivery_time.QUANTILES
    assert curve["late_pct"].between(0, 100).all()
    assert dt_metrics["test_mae_days"]["lightgbm_p50"] >= 0

    _, rr_metrics, scored = review_risk.train(feats)
    assert 0 <= rr_metrics["models"]["LightGBM (dispatch-time)"]["roc_auc"] <= 1
    assert scored["risk"].between(0, 1).all()

    series = forecast.daily_orders()
    assert series.index.is_monotonic_increasing and (series >= 0).all()
