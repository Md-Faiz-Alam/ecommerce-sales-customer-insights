-- Every completed delivery must have a lateness flag and a non-negative delivery time.
SELECT order_id
FROM marts.fact_orders
WHERE is_delivered AND (is_late IS NULL OR delivery_days < 0);
