-- fact_orders: grain = one order. The main table for KPIs, delivery and review analysis,
-- and the feature base for the ML models.
CREATE OR REPLACE TABLE marts.fact_orders AS
WITH items AS (
    SELECT
        order_id,
        count(*)                              AS item_count,
        count(DISTINCT seller_id)             AS seller_count,
        count(DISTINCT product_id)            AS product_count,
        sum(price)                            AS product_value,
        sum(freight_value)                    AS freight_value,
        sum(item_total)                       AS order_value,
        max(seller_customer_distance_km)      AS max_distance_km,
        arg_max(product_category, price)      AS main_category
    FROM marts.fact_order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        sum(payment_value)                    AS payment_value,
        arg_max(payment_type, payment_value)  AS main_payment_type,
        max(payment_installments)             AS installments,
        count(*)                              AS payment_count,
        bool_or(payment_type = 'voucher')     AS used_voucher
    FROM staging.payments
    GROUP BY order_id
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    c.customer_city,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.purchase_date::DATE                     AS purchase_date,
    o.purchase_month::DATE                    AS purchase_month,
    o.is_delivered,
    o.in_analysis_window,
    o.has_timestamp_anomaly,
    coalesce(i.item_count, 0)                 AS item_count,
    i.seller_count,
    i.product_count,
    i.main_category,
    coalesce(i.product_value, 0)              AS product_value,
    coalesce(i.freight_value, 0)              AS freight_value,
    coalesce(i.order_value, 0)                AS order_value,
    p.payment_value,
    p.main_payment_type,
    p.installments,
    p.payment_count,
    p.used_voucher,
    i.max_distance_km,
    o.approval_hours,
    o.delivery_days,
    o.estimated_delivery_days,
    o.delivery_delay_days,
    o.is_late,
    r.review_score,
    r.is_negative                             AS is_negative_review,
    r.has_comment                             AS review_has_comment,
    row_number() OVER (
        PARTITION BY c.customer_unique_id
        ORDER BY o.order_purchase_timestamp, o.order_id
    )                                         AS customer_order_seq
FROM staging.orders AS o
JOIN staging.customers AS c USING (customer_id)
LEFT JOIN items    AS i USING (order_id)
LEFT JOIN payments AS p USING (order_id)
LEFT JOIN staging.reviews AS r USING (order_id);
