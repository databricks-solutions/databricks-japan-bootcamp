-- Part2⑧-2: lb_tickets_history で自分の更新を見つける（保存から 15〜30 秒待って流す）
-- 実行場所: SQLエディタ（Databricks SQL）
-- 更新1回は update_preimage（変更前）と update_postimage（変更後）の2行になる。
-- _sort_by＝変更の並び順（同じ更新の2行は _pg_lsn が同じなので _sort_by で並べる）/ _timestamp＝Delta に書き出した時刻（UTC）
SELECT id, status, priority, owner,
       _pg_change_type, _timestamp
FROM <カタログ>.lab_<名前>.lb_tickets_history
ORDER BY _sort_by DESC LIMIT 10;
