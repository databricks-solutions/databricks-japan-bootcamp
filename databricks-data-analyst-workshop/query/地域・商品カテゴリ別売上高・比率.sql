USE CATALOG data_analyst_workshop;
USE SCHEMA bricksmart;

-- 地域・商品カテゴリ別売上高・比率
WITH region_sales AS (
  SELECT
    u.region,
    p.category,
    SUM(t.transaction_price) AS total_sales
  FROM
    transactions t
  JOIN
    users u ON t.user_id = u.user_id
  JOIN
    products p ON t.product_id = p.product_id
  WHERE
    t.transaction_price IS NOT NULL
    AND u.region IS NOT NULL
  GROUP BY
    u.region,
    p.category
),
total_region_sales AS (
  SELECT
    region,
    SUM(total_sales) AS region_total_sales
  FROM
    region_sales
  GROUP BY
    region
)
SELECT
  region_sales.region,
  region_sales.category,
  FLOOR(region_sales.total_sales),
  ROUND((region_sales.total_sales / total_region_sales.region_total_sales) * 100, 2) AS sales_ratio
FROM
  region_sales JOIN total_region_sales ON region_sales.region = total_region_sales.region
ORDER BY
  region_sales.region,
  region_sales.category
;