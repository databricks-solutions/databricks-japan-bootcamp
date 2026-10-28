-- T-SQL: 2026年7月の完了済み注文を顧客別に集計し、売上上位3件を返す。
-- 金額NULLは0、同額はcustomer_idの昇順。月初・月末を含む。
-- 架空の注文データ。実テーブルは不要。
WITH orders AS (
    SELECT 1 AS order_id, 'A' AS customer_id,
           CAST('2026-07-01' AS DATE) AS order_date,
           CAST(100.00 AS DECIMAL(12, 2)) AS amount, 'completed' AS status
    UNION ALL SELECT 2, 'A', CAST('2026-07-15' AS DATE), 50.00, 'completed'
    UNION ALL SELECT 3, 'B', CAST('2026-07-31' AS DATE), 200.00, 'completed'
    UNION ALL SELECT 4, 'B', CAST('2026-07-20' AS DATE), 999.00, 'cancelled'
    UNION ALL SELECT 5, 'C', CAST('2026-07-10' AS DATE), NULL, 'completed'
    UNION ALL SELECT 6, 'C', CAST('2026-07-10' AS DATE), 80.00, 'completed'
    UNION ALL SELECT 7, 'D', CAST('2026-07-25' AS DATE), 150.00, 'completed'
    UNION ALL SELECT 8, 'A', CAST('2026-06-30' AS DATE), 500.00, 'completed'
    UNION ALL SELECT 9, 'D', CAST('2026-08-01' AS DATE), 700.00, 'completed'
)
SELECT TOP (3)
    customer_id,
    COUNT(*) AS order_count,
    SUM(ISNULL(amount, 0)) AS total_amount
FROM orders
WHERE status = 'completed'
  AND order_date >= CONVERT(DATE, '2026-07-01', 23)
  AND order_date < DATEADD(MONTH, 1, CONVERT(DATE, '2026-07-01', 23))
GROUP BY customer_id
ORDER BY total_amount DESC, customer_id ASC;
