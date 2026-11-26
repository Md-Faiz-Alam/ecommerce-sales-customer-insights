-- Category Pareto / ABC analysis: which categories make up 80% of revenue?
-- A = top 80% of revenue, B = next 15%, C = last 5%.
CREATE OR REPLACE VIEW analysis.category_pareto AS
WITH by_category AS (
    SELECT
        product_category,
        count(DISTINCT order_id) AS orders,
        count(*)                 AS items,
        sum(item_total)          AS revenue,
        avg(price)               AS avg_price
    FROM marts.fact_order_items
    WHERE is_delivered AND in_analysis_window
    GROUP BY product_category
),
cumulative AS (
    SELECT
        *,
        revenue / sum(revenue) OVER ()                                              AS share,
        sum(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING) / sum(revenue) OVER () AS cum_share
    FROM by_category
)
SELECT
    dense_rank() OVER (ORDER BY revenue DESC)   AS revenue_rank,
    product_category,
    orders,
    items,
    round(revenue, 2)                           AS revenue,
    round(avg_price, 2)                         AS avg_price,
    round(100 * share, 2)                       AS revenue_share_pct,
    round(100 * cum_share, 2)                   AS cumulative_share_pct,
    CASE
        WHEN cum_share - share < 0.80 THEN 'A'
        WHEN cum_share - share < 0.95 THEN 'B'
        ELSE 'C'
    END                                         AS abc_class
FROM cumulative
ORDER BY revenue DESC;
