-- dim_customer: one row per real person (customer_unique_id).
-- Olist creates a new customer_id for every order, so this is the grain to use for
-- customer counts, retention and RFM. Location = address on the first order.
CREATE OR REPLACE TABLE marts.dim_customer AS
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        o.order_purchase_timestamp,
        o.is_delivered
    FROM staging.orders AS o
    JOIN staging.customers AS c USING (customer_id)
),
agg AS (
    SELECT
        customer_unique_id,
        arg_min(customer_zip_code_prefix, order_purchase_timestamp) AS zip_code_prefix,
        arg_min(customer_city, order_purchase_timestamp)            AS city,
        arg_min(customer_state, order_purchase_timestamp)           AS state,
        min(order_purchase_timestamp)                               AS first_order_at,
        max(order_purchase_timestamp)                               AS last_order_at,
        count(*)                                                    AS lifetime_orders,
        count(*) FILTER (WHERE is_delivered)                        AS lifetime_delivered_orders
    FROM customer_orders
    GROUP BY customer_unique_id
)
SELECT
    a.*,
    date_trunc('month', a.first_order_at)::DATE AS cohort_month,
    a.lifetime_orders > 1                       AS is_repeat_customer,
    g.lat,
    g.lng
FROM agg AS a
LEFT JOIN staging.geolocation AS g ON g.zip_code_prefix = a.zip_code_prefix;
