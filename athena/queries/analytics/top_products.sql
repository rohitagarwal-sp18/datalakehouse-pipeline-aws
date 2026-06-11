SELECT
    product_name,
    category,
    units_sold,
    total_revenue,
    order_count
FROM `datalakehouse-dev-gold`.top_products
ORDER BY total_revenue DESC;
