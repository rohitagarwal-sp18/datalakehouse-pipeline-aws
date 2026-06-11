SELECT
    sale_date,
    total_revenue,
    total_orders,
    ROUND(total_revenue / NULLIF(total_orders, 0), 2) AS avg_order_value
FROM `datalakehouse-dev-gold`.daily_sales
WHERE sale_date >= DATE_ADD('day', -30, CURRENT_DATE)
ORDER BY sale_date DESC;
