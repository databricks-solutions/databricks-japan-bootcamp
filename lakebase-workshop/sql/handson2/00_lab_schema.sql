-- 事前準備: 自分の作業場所（UC スキーマ）と 同期元のテーブル（顧客属性・Delta CDF つき）を作る
-- 実行場所: SQLエディタ（Databricks SQL）
-- 置き換え: <カタログ> = 演習用カタログ / <名前> = 自分の名前（英小文字と数字、先頭は英小文字）
-- 全員が自分の lab_<名前> に作る。作った人が所有者になる。何度流しても同じ状態になる
CREATE SCHEMA IF NOT EXISTS <カタログ>.lab_<名前>;
CREATE TABLE IF NOT EXISTS <カタログ>.lab_<名前>.customer_context (
  customer_name STRING NOT NULL, industry STRING, plan STRING,
  account_manager STRING, region STRING, support_tier STRING,
  updated_at TIMESTAMP) TBLPROPERTIES (delta.enableChangeDataFeed = true);
MERGE INTO <カタログ>.lab_<名前>.customer_context AS t USING (
  SELECT * FROM VALUES
  ('Sample Retail', '小売', 'Standard', 'Sales Rep A', '関東', 'Business'),
  ('Sample Foods', '食品', 'Enterprise', 'Sales Rep B', '関西', 'Premium'),
  ('Sample Manufacturing', '製造', 'Enterprise', 'Sales Rep C', '中部', 'Premium'),
  ('Sample Software', 'ソフトウェア', 'Standard', 'Sales Rep A', '関東', 'Business'),
  ('Sample Healthcare', 'ヘルスケア', 'Starter', 'Sales Rep D', '九州', 'Basic')
  AS v(customer_name, industry, plan, account_manager, region, support_tier)) AS s
ON t.customer_name = s.customer_name WHEN NOT MATCHED THEN INSERT
  (customer_name, industry, plan, account_manager, region, support_tier, updated_at)
  VALUES (s.customer_name, s.industry, s.plan, s.account_manager, s.region,
          s.support_tier, current_timestamp());

-- 件数を確かめる（5）
SELECT count(*) FROM <カタログ>.lab_<名前>.customer_context;
