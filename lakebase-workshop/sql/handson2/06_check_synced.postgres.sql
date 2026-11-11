-- Part2⑥-3: Lakebase で tickets と Synced Table を JOIN して値を確かめる
-- 実行場所: Lakebase の SQL Editor（自分のブランチ）
-- Synced Table は UC のスキーマ名のまま Postgres に現れる（public ではない）
SELECT t.id, t.customer, c.industry, c.plan,
       c.account_manager
FROM tickets t
LEFT JOIN lab_<名前>.customer_context_synced c
  ON c.customer_name = t.customer
ORDER BY t.id;
