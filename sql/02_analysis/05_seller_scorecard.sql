-- Seller scorecard: volume vs. quality, ranked, with an action quadrant.
-- Rates are only meaningful with enough volume; sellers with < 30 orders are labelled 'Low volume'.
CREATE OR REPLACE VIEW analysis.seller_scorecard AS
WITH seller_orders AS (
    SELECT seller_id, order_id, sum(item_total) AS seller_order_value
    FROM marts.fact_order_items
    WHERE in_analysis_window
    GROUP BY seller_id, order_id
),
metrics AS (
    SELECT
        so.seller_id,
        count(*)                                                        AS orders,
        count(*) FILTER (WHERE f.is_delivered)                          AS delivered_orders,
        sum(so.seller_order_value) FILTER (WHERE f.is_delivered)        AS revenue,
        avg(f.is_late::INT) FILTER (WHERE f.is_delivered)               AS late_rate,
        avg(f.review_score)                                             AS avg_review,
        avg(f.is_negative_review::INT)                                  AS negative_rate,
        avg((f.order_status = 'canceled')::INT)                         AS cancel_rate
    FROM seller_orders AS so
    JOIN marts.fact_orders AS f USING (order_id)
    GROUP BY so.seller_id
),
benchmarks AS (  -- medians among sellers with enough volume
    SELECT
        median(revenue)       AS median_revenue,
        median(negative_rate) AS median_negative_rate
    FROM metrics
    WHERE orders >= 30
)
SELECT
    m.seller_id,
    d.state                                         AS seller_state,
    d.city                                          AS seller_city,
    m.orders,
    m.delivered_orders,
    round(m.revenue, 2)                             AS revenue,
    round(100 * m.late_rate, 2)                     AS late_pct,
    round(m.avg_review, 2)                          AS avg_review,
    round(100 * m.negative_rate, 2)                 AS negative_review_pct,
    round(100 * m.cancel_rate, 2)                   AS cancel_pct,
    dense_rank() OVER (ORDER BY m.revenue DESC NULLS LAST) AS revenue_rank,
    CASE
        WHEN m.orders < 30 THEN 'Low volume'
        WHEN m.revenue >= b.median_revenue AND m.negative_rate <= b.median_negative_rate THEN 'Star: protect'
        WHEN m.revenue >= b.median_revenue                                                THEN 'High volume, poor quality: fix first'
        WHEN m.negative_rate <= b.median_negative_rate                                    THEN 'Quality, low volume: grow'
        ELSE 'Low volume, poor quality: review'
    END                                             AS action_quadrant
FROM metrics AS m
JOIN marts.dim_seller AS d USING (seller_id)
CROSS JOIN benchmarks AS b
ORDER BY m.revenue DESC NULLS LAST;
