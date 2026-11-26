USE ecommerce;

-- Row Counts
SELECT 'orders' AS table_name, COUNT(*) FROM orders
UNION ALL
SELECT 'customers', COUNT(*) FROM customers
UNION ALL
SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'payments', COUNT(*) FROM payments
UNION ALL
SELECT 'reviews', COUNT(*) FROM reviews;

-- Orders without customers
SELECT COUNT(*) AS missing_customers
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- Orders without payments
SELECT COUNT(*) AS missing_payments
FROM orders o
LEFT JOIN payments p ON o.order_id = p.order_id
WHERE p.order_id IS NULL;

-- Revenuse
SELECT SUM(payment_value) AS total_revenue
FROM payments;

-- Total Orders
SELECT COUNT(*) AS total_orders
FROM orders;

-- Total Customers
SELECT COUNT(DISTINCT customer_unique_id) AS total_customers
FROM customers;

-- Average Order Value (AOV)
SELECT 
    SUM(payment_value) / COUNT(DISTINCT order_id) AS avg_order_value
FROM payments;

-- Customer Lifetime Value (CLV) Analysis
SELECT 
    c.customer_unique_id,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(p.payment_value) AS total_spent,
    AVG(p.payment_value) AS avg_order_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY c.customer_unique_id
ORDER BY total_spent DESC
LIMIT 30;

-- Customer Segmentation
SELECT 
    c.customer_unique_id,
    SUM(p.payment_value) AS total_spent,
    CASE 
        WHEN SUM(p.payment_value) > 1000 THEN 'High Value'
        WHEN SUM(p.payment_value) BETWEEN 500 AND 1000 THEN 'Medium Value'
        ELSE 'Low Value'
    END AS customer_segment
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY c.customer_unique_id;

-- Product Analysis
SELECT 
    pr.product_category_name,
    SUM(oi.price) AS revenue
FROM order_items oi
JOIN products pr ON oi.product_id = pr.product_id
GROUP BY pr.product_category_name
ORDER BY revenue DESC
LIMIT 10;

-- Low Performing Products (hidden problem)
SELECT 
    product_id,
    SUM(price) AS revenue
FROM order_items
GROUP BY product_id
ORDER BY revenue ASC
LIMIT 10;

-- Delivery Analysis
SELECT 
    AVG(DATEDIFF(order_delivered_customer_date, order_purchase_timestamp)) AS avg_delivery_days
FROM orders
WHERE order_delivered_customer_date IS NOT NULL;

-- Late Delivery percent
SELECT 
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders WHERE order_status = 'delivered') AS late_delivery_percentage
FROM orders
WHERE order_delivered_customer_date > order_estimated_delivery_date;

-- Review Analysis (Customer Satisfaction)
SELECT 
    AVG(review_score) AS avg_rating
FROM reviews;






































































