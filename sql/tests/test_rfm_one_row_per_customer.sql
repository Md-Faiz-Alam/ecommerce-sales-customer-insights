-- RFM must be one row per customer, with every score in 1..5.
SELECT customer_unique_id, count(*) AS n
FROM analysis.customer_rfm
GROUP BY customer_unique_id
HAVING count(*) > 1
UNION ALL
SELECT customer_unique_id, 0
FROM analysis.customer_rfm
WHERE r_score NOT BETWEEN 1 AND 5 OR f_score NOT BETWEEN 1 AND 5 OR m_score NOT BETWEEN 1 AND 5;
