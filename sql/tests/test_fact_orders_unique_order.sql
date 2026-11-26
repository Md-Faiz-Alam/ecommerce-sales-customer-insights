-- fact_orders must have exactly one row per order.
SELECT order_id, count(*) AS n
FROM marts.fact_orders
GROUP BY order_id
HAVING count(*) > 1;
