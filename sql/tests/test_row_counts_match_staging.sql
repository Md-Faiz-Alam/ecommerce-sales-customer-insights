-- Marts must not gain or lose rows versus staging (a bad join would do either).
SELECT 'fact_orders' AS model, (SELECT count(*) FROM marts.fact_orders) AS mart_rows,
       (SELECT count(*) FROM staging.orders) AS staging_rows
WHERE (SELECT count(*) FROM marts.fact_orders) <> (SELECT count(*) FROM staging.orders)
UNION ALL
SELECT 'fact_order_items', (SELECT count(*) FROM marts.fact_order_items),
       (SELECT count(*) FROM staging.order_items)
WHERE (SELECT count(*) FROM marts.fact_order_items) <> (SELECT count(*) FROM staging.order_items)
UNION ALL
SELECT 'dim_customer', (SELECT count(*) FROM marts.dim_customer),
       (SELECT count(DISTINCT customer_unique_id) FROM staging.customers)
WHERE (SELECT count(*) FROM marts.dim_customer)
   <> (SELECT count(DISTINCT customer_unique_id) FROM staging.customers);
