USE CATALOG data_analyst_workshop;
USE SCHEMA bricksmart;

-- ローデータ確認
SELECT * FROM users LIMIT 10;
SELECT * FROM products LIMIT 10;
SELECT * FROM transactions LIMIT 10;

-- メトリクスビュー確認
SELECT 
  MEASURE(`total_purchace_amount`) AS `total_purchace_amount`, 
  MEASURE(`total_purchase_count`) AS `total_purchase_count`, 
  MEASURE(`total_unique_users`) AS `total_unique_users`, 
  MEASURE(`unit_price`) AS `unit_price`, 
  MEASURE(`frequency`) AS `frequency` 
FROM orders_metric_view LIMIT 10;