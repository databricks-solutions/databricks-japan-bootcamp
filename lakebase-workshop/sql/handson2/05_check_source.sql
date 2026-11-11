-- Part2⑤-1: 同期元（事前準備で作った lab_<名前>.customer_context）の Delta CDF と件数を確かめる
-- 実行場所: SQLエディタ（Databricks SQL）
-- 置き換え: <カタログ> = 演習用カタログ / <名前> = 自分の名前
-- テーブルが無い・false のときは 00_lab_schema.sql を流す

-- 1. Delta CDF が有効か確かめる（true なら OK）
SHOW TBLPROPERTIES <カタログ>.lab_<名前>
  .customer_context ('delta.enableChangeDataFeed');

-- 2. 件数を確かめる（5行）
SELECT count(*) FROM <カタログ>.lab_<名前>.customer_context;
