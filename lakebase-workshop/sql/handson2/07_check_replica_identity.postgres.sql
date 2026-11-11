-- Part2⑦-1: REPLICA IDENTITY が FULL（f）か確かめる
-- 実行場所: Lakebase の SQL Editor（自分のブランチ）
-- f でなければ 01_replica_identity.postgres.sql の ALTER を自分のブランチで流す
SELECT relname, relreplident FROM pg_class
 WHERE relname IN ('tickets', 'ticket_comments')
 ORDER BY relname;
