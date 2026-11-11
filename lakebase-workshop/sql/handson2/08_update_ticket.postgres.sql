-- Part2⑧-1: アプリが動かないときに SQL で同じ更新をする（更新したチケットの ID をメモする）
-- 実行場所: Lakebase の SQL Editor（自分のブランチ）
UPDATE tickets SET status = 'resolved', priority = 'high',
  updated_at = NOW() WHERE id = <メモした ID>;  -- 例 5
