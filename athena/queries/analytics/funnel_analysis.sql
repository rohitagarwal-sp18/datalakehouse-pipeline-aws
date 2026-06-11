SELECT
    event_date,
    unique_sessions,
    product_views,
    cart_views,
    total_orders,
    product_to_cart_rate,
    cart_to_purchase_rate
FROM `datalakehouse-dev-gold`.funnel_analysis
WHERE event_date >= DATE_ADD('day', -30, CURRENT_DATE)
ORDER BY event_date DESC;
