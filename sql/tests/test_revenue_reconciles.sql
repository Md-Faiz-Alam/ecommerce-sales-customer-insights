-- Order-level revenue must equal item-level revenue (to the cent).
SELECT
    (SELECT sum(order_value) FROM marts.fact_orders)     AS order_level,
    (SELECT sum(item_total) FROM staging.order_items)    AS item_level
WHERE abs((SELECT sum(order_value) FROM marts.fact_orders)
        - (SELECT sum(item_total) FROM staging.order_items)) > 0.01;
