USE CATALOG data_analyst_workshop;
USE SCHEMA bricksmart;

-- 性別・商品カテゴリ別売上高・比率
WITH gender_sales AS (
  SELECT
    u.gender,
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
    AND u.gender IS NOT NULL
  GROUP BY
    u.gender,
    p.category
),
total_gender_sales AS (
  SELECT
    gender,
    SUM(total_sales) AS gender_total_sales
  FROM
    gender_sales
  GROUP BY
    gender
)
SELECT
  gender_sales.gender,
  gender_sales.category,
  FLOOR(gender_sales.total_sales),
  ROUND((gender_sales.total_sales / total_gender_sales.gender_total_sales) * 100, 2) AS sales_ratio
FROM
  gender_sales
JOIN
  total_gender_sales ON gender_sales.gender = total_gender_sales.gender
ORDER BY
  gender_sales.gender,
  gender_sales.category
;