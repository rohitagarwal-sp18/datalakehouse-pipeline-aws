SELECT
    email,
    total_orders,
    total_revenue,
    avg_order_value,
    days_as_customer
FROM `datalakehouse-dev-gold`.customer_ltv
ORDER BY total_revenue DESC
LIMIT 100;
