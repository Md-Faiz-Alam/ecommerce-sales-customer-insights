-- RFM segmentation (Recency, Frequency, Monetary) on delivered orders.
-- Frequency uses fixed buckets, not NTILE: ~97% of customers have exactly one order, so
-- quintiles of frequency would be meaningless. R and M use quintiles (NTILE(5)); ties are broken
-- by customer_unique_id so segment counts are reproducible run to run.
CREATE OR REPLACE VIEW analysis.customer_rfm AS
WITH base AS (
    SELECT
        customer_unique_id,
        max(purchase_date) AS last_purchase_date,
        count(*)           AS frequency,
        sum(order_value)   AS monetary
    FROM marts.fact_orders
    WHERE is_delivered AND in_analysis_window
    GROUP BY customer_unique_id
),
ref AS (
    SELECT max(purchase_date) + 1 AS as_of_date FROM marts.fact_orders WHERE in_analysis_window
),
scored AS (
    SELECT
        b.*,
        date_diff('day', b.last_purchase_date, r.as_of_date)                      AS recency_days,
        ntile(5) OVER (
            ORDER BY date_diff('day', b.last_purchase_date, r.as_of_date) DESC, b.customer_unique_id
        )                                                                         AS r_score,
        CASE WHEN b.frequency >= 3 THEN 5 WHEN b.frequency = 2 THEN 4 ELSE 1 END  AS f_score,
        ntile(5) OVER (ORDER BY b.monetary, b.customer_unique_id)                 AS m_score
    FROM base AS b
    CROSS JOIN ref AS r
)
SELECT
    customer_unique_id,
    last_purchase_date,
    recency_days,
    frequency,
    round(monetary, 2)                              AS monetary,
    r_score,
    f_score,
    m_score,
    concat(r_score, f_score, m_score)               AS rfm_code,
    CASE
        WHEN f_score >= 4 AND r_score >= 4 THEN 'Champions'
        WHEN f_score >= 4                  THEN 'Loyal, lapsing'
        WHEN r_score >= 4 AND m_score >= 4 THEN 'New high-value'
        WHEN r_score >= 4                  THEN 'New low-value'
        WHEN r_score <= 2 AND m_score >= 4 THEN 'At-risk big spenders'
        WHEN r_score <= 2                  THEN 'Hibernating'
        ELSE 'Needs attention'
    END                                             AS segment
FROM scored;


CREATE OR REPLACE VIEW analysis.rfm_segment_summary AS
SELECT
    segment,
    count(*)                                                    AS customers,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)          AS customer_share_pct,
    round(sum(monetary), 2)                                     AS revenue,
    round(100.0 * sum(monetary) / sum(sum(monetary)) OVER (), 2) AS revenue_share_pct,
    round(avg(monetary), 2)                                     AS avg_monetary,
    round(avg(recency_days), 0)                                 AS avg_recency_days,
    round(avg(frequency), 2)                                    AS avg_frequency
FROM analysis.customer_rfm
GROUP BY segment
ORDER BY revenue DESC;
