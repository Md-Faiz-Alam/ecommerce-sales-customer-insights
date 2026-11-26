-- Monthly KPI trend with MoM / YoY growth, running total and 3-month moving average.
-- Business question: is the business growing, and is operational quality keeping up?
CREATE SCHEMA IF NOT EXISTS analysis;

CREATE OR REPLACE VIEW analysis.kpi_monthly AS
WITH monthly AS (
    SELECT
        purchase_month                                               AS month,
        count(*)                                                     AS orders,
        count(*) FILTER (WHERE is_delivered)                         AS delivered_orders,
        count(DISTINCT customer_unique_id)                           AS customers,
        sum(order_value) FILTER (WHERE is_delivered)                 AS revenue,
        avg(is_late::INT) FILTER (WHERE is_delivered)                AS late_rate,
        avg(review_score)                                            AS avg_review,
        avg(delivery_days) FILTER (WHERE is_delivered)               AS avg_delivery_days,
        count(*) FILTER (WHERE order_status IN ('canceled', 'unavailable')) AS lost_orders
    FROM marts.fact_orders
    WHERE in_analysis_window
    GROUP BY purchase_month
)
SELECT
    month,
    orders,
    delivered_orders,
    customers,
    round(revenue, 2)                                                       AS revenue,
    round(revenue / delivered_orders, 2)                                    AS aov,
    round(100 * (revenue / lag(revenue) OVER w - 1), 2)                     AS revenue_mom_pct,
    round(100 * (revenue / lag(revenue, 12) OVER w - 1), 2)                 AS revenue_yoy_pct,
    round(sum(revenue) OVER (w ROWS UNBOUNDED PRECEDING), 2)                AS cumulative_revenue,
    round(avg(revenue) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS revenue_3m_avg,
    round(100 * late_rate, 2)                                               AS late_pct,
    round(avg_review, 2)                                                    AS avg_review,
    round(avg_delivery_days, 1)                                             AS avg_delivery_days,
    round(100 * lost_orders / orders, 2)                                    AS lost_order_pct
FROM monthly
WINDOW w AS (ORDER BY month)
ORDER BY month;
