INSERT OR IGNORE INTO tickets (id, title, customer, status, priority, owner, category, description, created_at, updated_at)
VALUES
    (101, '[DEMO] Lakebase接続前の確認チケット', 'Sample Company', 'new', 'medium', 'Demo User', 'Demo Mode', 'このチケットはSQLiteデモモード専用です。Lakebase接続後は表示されません。', datetime('now', '-2 days'), datetime('now', '-2 days')),
    (102, '[DEMO] アプリ画面の操作確認', 'Sample Company', 'in_progress', 'low', 'Demo User', 'Demo Mode', 'ステータス変更やコメント追加など、アプリ自体の動作を確認するためのデータです。', datetime('now', '-1 day'), datetime('now', '-4 hours')),
    (103, '[DEMO] 接続バッジを確認してください', 'Sample Company', 'waiting', 'high', 'Demo User', 'Demo Mode', '画面右上が黄色のデモモード表示であることを確認してください。', datetime('now', '-8 hours'), datetime('now', '-1 hour'));

INSERT OR IGNORE INTO ticket_comments (id, ticket_id, author, body, created_at)
VALUES
    (101, 101, 'Demo User', 'Lakebase接続後は別の5件のチケットへ切り替わります。', datetime('now', '-1 day')),
    (102, 102, 'Demo User', 'このコメントもSQLiteデモモード専用です。', datetime('now', '-3 hours'));
