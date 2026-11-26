"""Export a clean star schema for Power BI (CSV, business-friendly column names).

Run:  python -m ecom.export_bi      ->  data/powerbi/*.csv

Design choices:
- Only the analysis window (Jan 2017 - Aug 2018) is exported, so trends have no fake head/tail.
- Every metric is defined once (reports/metrics.md); Power BI only aggregates.
- RFM segment and seller scorecard are joined onto their dimensions, so slicers just work.
- Delivery-timing buckets carry a sort column, so charts sort in business order, not A-Z.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ecom.config import DATA_DIR
from ecom.db import query

log = logging.getLogger("ecom.export_bi")
OUT_DIR = DATA_DIR / "powerbi"

TABLES: dict[str, str] = {
    "Orders": """
        SELECT
            order_id                        AS "Order ID",
            customer_unique_id              AS "Customer ID",
            customer_state                  AS "Customer State",
            order_status                    AS "Status",
            purchase_date                   AS "Purchase Date",
            order_purchase_timestamp        AS "Purchase Timestamp",
            is_delivered                    AS "Is Delivered",
            is_late                         AS "Is Late",
            replace(main_category, '_', ' ') AS "Main Category",
            item_count                      AS "Items",
            order_value                     AS "Order Value",
            freight_value                   AS "Freight Value",
            main_payment_type               AS "Payment Type",
            installments                    AS "Installments",
            round(delivery_days, 2)         AS "Delivery Days",
            round(estimated_delivery_days, 2) AS "Promised Days",
            delivery_delay_days             AS "Delay Days",
            CASE
                WHEN NOT is_delivered            THEN 'Not delivered'
                WHEN delivery_delay_days <= -8   THEN '8+ days early'
                WHEN delivery_delay_days <= -1   THEN '1-7 days early'
                WHEN delivery_delay_days = 0     THEN 'On promised day'
                WHEN delivery_delay_days <= 3    THEN '1-3 days late'
                WHEN delivery_delay_days <= 7    THEN '4-7 days late'
                ELSE '8+ days late'
            END                             AS "Delivery Timing",
            CASE
                WHEN NOT is_delivered            THEN 7
                WHEN delivery_delay_days <= -8   THEN 1
                WHEN delivery_delay_days <= -1   THEN 2
                WHEN delivery_delay_days = 0     THEN 3
                WHEN delivery_delay_days <= 3    THEN 4
                WHEN delivery_delay_days <= 7    THEN 5
                ELSE 6
            END                             AS "Delivery Timing Sort",
            review_score                    AS "Review Score",
            is_negative_review              AS "Is Negative Review",
            customer_order_seq              AS "Customer Order Number",
            round(max_distance_km, 0)       AS "Distance km"
        FROM marts.fact_orders
        WHERE in_analysis_window
        ORDER BY purchase_date, order_id
    """,
    "Order Items": """
        SELECT
            i.order_id          AS "Order ID",
            i.order_item_id     AS "Item Number",
            i.product_id        AS "Product ID",
            i.seller_id         AS "Seller ID",
            i.price             AS "Price",
            i.freight_value     AS "Freight Value",
            i.item_total        AS "Item Total"
        FROM marts.fact_order_items i
        WHERE i.in_analysis_window
        ORDER BY i.order_id, i.order_item_id
    """,
    "Customers": """
        SELECT
            c.customer_unique_id        AS "Customer ID",
            c.city                      AS "City",
            c.state                     AS "State",
            c.first_order_at::DATE      AS "First Order Date",
            c.cohort_month              AS "Cohort Month",
            c.lifetime_orders           AS "Lifetime Orders",
            c.is_repeat_customer        AS "Is Repeat Customer",
            coalesce(r.segment, 'No delivered order') AS "RFM Segment",
            r.r_score                   AS "Recency Score",
            r.f_score                   AS "Frequency Score",
            r.m_score                   AS "Monetary Score",
            r.monetary                  AS "Lifetime Revenue"
        FROM marts.dim_customer c
        LEFT JOIN analysis.customer_rfm r USING (customer_unique_id)
        WHERE c.customer_unique_id IN (
            SELECT customer_unique_id FROM marts.fact_orders WHERE in_analysis_window
        )
        ORDER BY 1
    """,
    "Products": """
        SELECT
            product_id                  AS "Product ID",
            replace(product_category, '_', ' ') AS "Category",
            product_category_pt         AS "Category (PT)",
            product_weight_g            AS "Weight g",
            product_photos_qty          AS "Photos"
        FROM marts.dim_product
        ORDER BY 1
    """,
    "Sellers": """
        SELECT
            s.seller_id                 AS "Seller ID",
            s.city                      AS "City",
            s.state                     AS "State",
            sc.orders                   AS "Orders (window)",
            sc.revenue                  AS "Revenue (window)",
            sc.late_pct / 100           AS "Late Rate",
            sc.negative_review_pct / 100 AS "Negative Review Rate",
            sc.avg_review               AS "Avg Review",
            sc.revenue_rank             AS "Revenue Rank",
            coalesce(sc.action_quadrant, 'No orders in window') AS "Action Quadrant"
        FROM marts.dim_seller s
        LEFT JOIN analysis.seller_scorecard sc USING (seller_id)
        ORDER BY 1
    """,
    "Date": """
        SELECT
            date_key                    AS "Date",
            year                        AS "Year",
            quarter                     AS "Quarter",
            month                       AS "Month Number",
            month_name                  AS "Month",
            month_start                 AS "Month Start",
            strftime(date_key, '%b %Y') AS "Month Year",
            year * 100 + month          AS "Month Year Sort",
            week_start                  AS "Week Start",
            day_name                    AS "Weekday",
            day_of_week                 AS "Weekday Sort",
            is_weekend                  AS "Is Weekend"
        FROM marts.dim_date
        WHERE date_key BETWEEN DATE '2017-01-01' AND DATE '2018-08-31'
        ORDER BY 1
    """,
    "Cohort Retention": """
        SELECT
            cohort_month                AS "Cohort Month",
            strftime(cohort_month, '%Y-%m') AS "Cohort",
            months_since_first          AS "Months Since First Order",
            cohort_size                 AS "Cohort Size",
            active_customers            AS "Active Customers",
            retention_pct / 100         AS "Retention Rate"
        FROM analysis.cohort_retention
        ORDER BY 1, 3
    """,
}


def _forecast_table() -> pd.DataFrame:
    """Last 8 weeks of actual daily orders + the 28-day ensemble forecast (notebook 08)."""
    from ecom.models import forecast

    series = forecast.daily_orders()
    fut = forecast.forecast_future(series)
    actual = series.iloc[-56:].rename("Actual Orders").to_frame()
    names = {
        "forecast": "Forecast Orders",
        "low_80": "Forecast Low (80%)",
        "high_80": "Forecast High (80%)",
    }
    out = pd.concat([actual, fut.rename(columns=names).round(0)])
    return out.rename_axis("Date").reset_index()


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Make CSVs import cleanly: date-only columns without 00:00:00, no float noise."""
    df = df.copy()
    for col in df.select_dtypes("datetime").columns:
        s = df[col]
        if s.dropna().eq(s.dropna().dt.normalize()).all():
            df[col] = s.dt.strftime("%Y-%m-%d")
    for col in df.select_dtypes("float").columns:
        df[col] = df[col].round(4 if "Rate" in col else 2)
    return df


def export(out_dir: Path = OUT_DIR) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    frames = {name: query(sql) for name, sql in TABLES.items()}
    frames["Forecast"] = _forecast_table()
    for name, df in frames.items():
        tidy(df).to_csv(out_dir / f"{name}.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
        counts[name] = len(df)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")  # fmt: skip
    for name, n in export().items():
        log.info("  %-18s %8s rows", name, f"{n:,}")
    log.info("Power BI files -> %s", OUT_DIR)


if __name__ == "__main__":
    main()
