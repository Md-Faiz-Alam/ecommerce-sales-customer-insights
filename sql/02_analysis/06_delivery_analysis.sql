-- Delivery performance by customer state: where are deliveries slow, late and expensive?
CREATE OR REPLACE VIEW analysis.state_delivery AS
SELECT
    customer_state                                          AS state,
    count(*)                                                AS delivered_orders,
    round(avg(delivery_days), 1)                            AS avg_delivery_days,
    round(median(delivery_days), 1)                         AS median_delivery_days,
    round(avg(estimated_delivery_days), 1)                  AS avg_promised_days,
    round(100 * avg(is_late::INT), 2)                       AS late_pct,
    round(avg(freight_value), 2)                            AS avg_freight,
    round(100 * sum(freight_value) / sum(order_value), 2)   AS freight_share_pct,
    round(avg(max_distance_km), 0)                          AS avg_distance_km,
    round(avg(review_score), 2)                             AS avg_review
FROM marts.fact_orders
WHERE is_delivered AND in_analysis_window
GROUP BY customer_state
ORDER BY late_pct DESC;


-- How review scores change with delivery delay vs. the promised date.
CREATE OR REPLACE VIEW analysis.delivery_vs_review AS
WITH bucketed AS (
    SELECT
        CASE
            WHEN delivery_delay_days <= -15 THEN 1
            WHEN delivery_delay_days <= -8  THEN 2
            WHEN delivery_delay_days <= -1  THEN 3
            WHEN delivery_delay_days = 0    THEN 4
            WHEN delivery_delay_days <= 3   THEN 5
            WHEN delivery_delay_days <= 7   THEN 6
            WHEN delivery_delay_days <= 14  THEN 7
            ELSE 8
        END AS bucket_order,
        review_score,
        is_negative_review,
        review_has_comment
    FROM marts.fact_orders
    WHERE is_delivered AND in_analysis_window AND review_score IS NOT NULL
)
SELECT
    bucket_order,
    CASE bucket_order
        WHEN 1 THEN '15+ days early'
        WHEN 2 THEN '8-14 days early'
        WHEN 3 THEN '1-7 days early'
        WHEN 4 THEN 'On promised day'
        WHEN 5 THEN '1-3 days late'
        WHEN 6 THEN '4-7 days late'
        WHEN 7 THEN '8-14 days late'
        ELSE '15+ days late'
    END                                                     AS delivery_timing,
    count(*)                                                AS orders,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)      AS order_share_pct,
    round(avg(review_score), 2)                             AS avg_review,
    round(100 * avg(is_negative_review::INT), 2)            AS negative_review_pct,
    round(100 * avg(review_has_comment::INT), 2)            AS commented_pct
FROM bucketed
GROUP BY bucket_order
ORDER BY bucket_order;
