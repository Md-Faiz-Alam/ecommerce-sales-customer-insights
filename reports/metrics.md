# Metric Definitions

One definition per metric, used by SQL, notebooks, Power BI and the app. If a number in this
project doesn't match a definition below, that's a bug.

All money is in **Brazilian reais (BRL, R$)**. Unless stated otherwise, metrics are computed on
the **analysis window** (orders purchased 2017-01-01 to 2018-08-31, `in_analysis_window = true`).

## Orders & revenue

| Metric | Definition | Source |
|---|---|---|
| **Order** | One `order_id`. All statuses unless stated otherwise | `marts.fact_orders` |
| **Completed order** | `is_delivered = true`: status `delivered` **and** a delivery timestamp exists | `fact_orders.is_delivered` |
| **Revenue** | Sum of `price + freight_value` over items of **completed** orders. Canceled or unavailable orders are not revenue | `fact_orders.order_value` |
| **Product revenue** | Sum of `price` only (excludes freight) | `fact_orders.product_value` |
| **Payment value** | Sum of payments. Differs from revenue by installment interest; agrees within R$1 on 99.7% of orders (tested) | `fact_orders.payment_value` |
| **AOV** | Revenue / completed orders | `analysis.kpi_monthly.aov` |
| **Lost order rate** | Orders with status `canceled` or `unavailable` / all orders | `analysis.kpi_monthly.lost_order_pct` |

## Customers

| Metric | Definition |
|---|---|
| **Customer** | One `customer_unique_id`. Olist's `customer_id` is regenerated per order and must not be used to count people |
| **Cohort month** | Month of a customer's first order (any status) |
| **Repeat customer** | Customer with 2 or more orders (any status) |
| **Retention (month N)** | Share of a cohort that placed an order N months after its cohort month |
| **RFM** | Recency = days since last completed order (as of the day after the window ends); Frequency = completed orders; Monetary = revenue. R and M use quintiles; F uses fixed buckets (1 → 1, 2 → 4, 3+ → 5) because 97% of customers buy once |

## Delivery & satisfaction

| Metric | Definition |
|---|---|
| **Delivery days** | `order_delivered_customer_date - order_purchase_timestamp`, in fractional days |
| **Promised days** | `order_estimated_delivery_date - order_purchase_timestamp` |
| **Delay days** | Delivery **calendar date** minus promised **calendar date**. Negative = early |
| **Late order** | Completed order with delay days > 0, i.e. it arrived on a later day than promised |
| **Late rate** | Late orders / completed orders |
| **Negative review** | `review_score <= 2` |
| **Avg review** | Mean `review_score` over orders that have a review (one review per order: the latest) |

## Sellers & categories

| Metric | Definition |
|---|---|
| **Seller revenue** | Sum of that seller's items in completed orders (an order can have several sellers) |
| **Rated seller** | Seller with 30 or more orders in the window. Rates for smaller sellers are too noisy to rank |
| **Seller quadrant** | Volume = revenue vs. median of rated sellers; quality = negative review rate vs. median of rated sellers |
| **ABC class** | Categories ranked by revenue: A = first 80% of cumulative revenue, B = next 15%, C = last 5% |
