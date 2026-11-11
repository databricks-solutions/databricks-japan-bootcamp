-- Part2⑧-4: 履歴を「今の状態」に畳み込み 顧客属性と JOIN して集計する
-- 実行場所: SQLエディタ（Databricks SQL）
-- updates_total は ⑧で保存した回数と同じになる（1回なら 1）
WITH latest AS (
  SELECT * FROM <カタログ>.lab_<名前>.lb_tickets_history
  WHERE _pg_change_type IN ('insert', 'update_postimage', 'delete')
  QUALIFY row_number() OVER (PARTITION BY id ORDER BY _sort_by DESC) = 1
)
SELECT c.plan, l.status, count(*) AS tickets,
       (SELECT count(*) FROM <カタログ>.lab_<名前>.lb_tickets_history h
         WHERE h._pg_change_type = 'update_postimage') AS updates_total
FROM latest l
JOIN <カタログ>.lab_<名前>.customer_context c ON c.customer_name = l.customer
WHERE l._pg_change_type <> 'delete'
GROUP BY c.plan, l.status
ORDER BY c.plan, l.status;
