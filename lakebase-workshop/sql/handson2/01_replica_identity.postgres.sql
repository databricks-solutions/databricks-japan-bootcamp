-- シードデータの投入（../schema.postgres.sql と ../seed.postgres.sql）に続けて流す
-- 実行場所: Lakebase の SQL Editor（自分のプロジェクトの production）
-- 変更履歴（Lakebase CDF）に要る設定。production で設定すると、あとで作るブランチに引き継がれる
ALTER TABLE tickets REPLICA IDENTITY FULL;
ALTER TABLE ticket_comments REPLICA IDENTITY FULL;

-- 件数を確かめる（5 と 3）
SELECT (SELECT count(*) FROM tickets) AS tickets,
       (SELECT count(*) FROM ticket_comments) AS ticket_comments;
