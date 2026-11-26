-- dim_date: one row per calendar day, covering purchases through the last delivery.
-- in_analysis_window comes from staging.orders, so it has a single source of truth (ecom/config.py).
CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE TABLE marts.dim_date AS
WITH bounds AS (
    SELECT
        min(purchase_date)::DATE AS first_day,
        greatest(max(order_estimated_delivery_date), max(order_delivered_customer_date))::DATE AS last_day,
        min(purchase_date) FILTER (WHERE in_analysis_window)::DATE AS window_start,
        max(purchase_date) FILTER (WHERE in_analysis_window)::DATE AS window_end
    FROM staging.orders
),
days AS (
    SELECT unnest(generate_series(first_day, last_day, INTERVAL 1 DAY))::DATE AS d, window_start, window_end
    FROM bounds
)
SELECT
    d                                   AS date_key,
    year(d)                             AS year,
    quarter(d)                          AS quarter,
    month(d)                            AS month,
    strftime(d, '%b')                   AS month_name,
    date_trunc('month', d)::DATE        AS month_start,
    date_trunc('week', d)::DATE         AS week_start,
    isodow(d)                           AS day_of_week,     -- 1 = Monday
    strftime(d, '%a')                   AS day_name,
    isodow(d) IN (6, 7)                 AS is_weekend,
    d BETWEEN window_start AND window_end AS in_analysis_window
FROM days;
