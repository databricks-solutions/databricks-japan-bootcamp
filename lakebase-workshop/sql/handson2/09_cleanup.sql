-- 片付け: 自分の UC スキーマを消す（同期元と変更履歴のテーブルも消える。Synced Table と Lakebase CDF を先に消してから）
-- 実行場所: SQLエディタ（Databricks SQL）
DROP SCHEMA <カタログ>.lab_<名前> CASCADE;
