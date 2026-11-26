-- Monthly acquisition cohorts: % of each cohort that orders again N months after their first order.
-- Business question: do customers come back?
CREATE OR REPLACE VIEW analysis.cohort_retention AS
WITH window_start AS (
    SELECT min(purchase_month) AS first_month FROM marts.fact_orders WHERE in_analysis_window
),
activity AS (
    SELECT DISTINCT
        f.customer_unique_id,
        d.cohort_month,
        date_diff('month', d.cohort_month, f.purchase_month) AS months_since_first
    FROM marts.fact_orders AS f
    JOIN marts.dim_customer AS d USING (customer_unique_id)
    CROSS JOIN window_start AS w
    WHERE f.in_analysis_window
      AND d.cohort_month >= w.first_month          -- only cohorts fully observed in the window
),
cohort_size AS (
    SELECT cohort_month, count(*) AS cohort_size
    FROM activity
    WHERE months_since_first = 0
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    a.months_since_first,
    s.cohort_size,
    count(*)                                AS active_customers,
    round(100.0 * count(*) / s.cohort_size, 2) AS retention_pct
FROM activity AS a
JOIN cohort_size AS s USING (cohort_month)
GROUP BY a.cohort_month, a.months_since_first, s.cohort_size
ORDER BY a.cohort_month, a.months_since_first;


-- Headline repeat-purchase stats (whole customer base, all statuses).
CREATE OR REPLACE VIEW analysis.repeat_purchase_summary AS
WITH second_orders AS (
    SELECT
        customer_unique_id,
        date_diff('day',
            min(order_purchase_timestamp) FILTER (WHERE customer_order_seq = 1),
            min(order_purchase_timestamp) FILTER (WHERE customer_order_seq = 2)
        ) AS days_to_second_order
    FROM marts.fact_orders
    GROUP BY customer_unique_id
)
SELECT
    count(*)                                                  AS customers,
    count(*) FILTER (WHERE days_to_second_order IS NOT NULL)  AS repeat_customers,
    round(100.0 * count(*) FILTER (WHERE days_to_second_order IS NOT NULL) / count(*), 2)
                                                              AS repeat_rate_pct,
    median(days_to_second_order)                              AS median_days_to_second_order,
    round(100.0 * count(*) FILTER (WHERE days_to_second_order = 0)
        / nullif(count(*) FILTER (WHERE days_to_second_order IS NOT NULL), 0), 2)
                                                              AS same_day_repeat_pct
FROM second_orders;
