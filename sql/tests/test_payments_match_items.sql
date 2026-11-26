-- Payments and item totals must agree within R$1 for >= 99% of delivered orders.
-- (Small gaps are installment interest / voucher rounding; a big gap means a broken join.)
SELECT round(100 * avg((abs(payment_value - order_value) > 1)::INT), 2) AS pct_mismatched
FROM marts.fact_orders
WHERE is_delivered AND payment_value IS NOT NULL
HAVING avg((abs(payment_value - order_value) > 1)::INT) > 0.01;
