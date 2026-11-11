-- Part2⑥-1: 同期元の plan を Enterprise に変える（このあと 同期テーブルの 今すぐ同期 を押す）
-- 実行場所: SQLエディタ（Databricks SQL）
-- 置き換え: <カタログ> = 演習用カタログ / <名前> = 自分の名前

-- 1. 同期元を更新する
UPDATE <カタログ>.lab_<名前>.customer_context
SET plan = 'Enterprise', updated_at = current_timestamp()
WHERE customer_name = 'Sample Retail';

-- 2. 更新されたことを確かめる
SELECT customer_name, plan, updated_at FROM
  <カタログ>.lab_<名前>.customer_context ORDER BY customer_name;
