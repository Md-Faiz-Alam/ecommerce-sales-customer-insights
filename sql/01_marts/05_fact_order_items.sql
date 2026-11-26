-- fact_order_items: grain = one item line in an order (order_id, order_item_id).
-- Revenue at item level = price + freight_value (see docs/metrics.md).
CREATE OR REPLACE TABLE marts.fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    c.customer_unique_id,
    o.purchase_date::DATE  AS purchase_date,
    o.purchase_month::DATE AS purchase_month,
    o.order_status,
    o.is_delivered,
    o.in_analysis_window,
    p.product_category,
    i.price,
    i.freight_value,
    i.item_total,
    i.shipping_limit_date,
    -- Great-circle (haversine) distance between seller and customer zip centroids.
    CASE WHEN cg.lat IS NOT NULL AND sg.lat IS NOT NULL THEN
        2 * 6371 * asin(sqrt(
            pow(sin(radians(sg.lat - cg.lat) / 2), 2)
            + cos(radians(cg.lat)) * cos(radians(sg.lat)) * pow(sin(radians(sg.lng - cg.lng) / 2), 2)
        ))
    END AS seller_customer_distance_km
FROM staging.order_items AS i
JOIN staging.orders    AS o USING (order_id)
JOIN staging.customers AS c USING (customer_id)
JOIN staging.products  AS p USING (product_id)
JOIN staging.sellers   AS s USING (seller_id)
LEFT JOIN staging.geolocation AS cg ON cg.zip_code_prefix = c.customer_zip_code_prefix
LEFT JOIN staging.geolocation AS sg ON sg.zip_code_prefix = s.seller_zip_code_prefix;
