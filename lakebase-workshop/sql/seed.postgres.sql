INSERT INTO tickets (id, title, customer, status, priority, owner, category, description, created_at, updated_at)
VALUES
    (1, 'ダッシュボードの表示が遅い', 'Sample Retail', 'new', 'high', 'Demo User 1', 'Performance', '月次ダッシュボードの初回表示に 20 秒以上かかる。営業会議前に改善状況を確認したい。', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'),
    (2, 'CSV エクスポートに古い列名が出る', 'Sample Foods', 'in_progress', 'medium', 'Demo User 2', 'Data Quality', '顧客一覧の CSV に deprecated_customer_id が残っている。アプリ画面側では非表示になっている。', NOW() - INTERVAL '3 days', NOW() - INTERVAL '1 day'),
    (3, '新規ユーザーがコメントを追加できない', 'Sample Manufacturing', 'waiting', 'urgent', 'Demo User 3', 'Access Control', '権限付与直後のユーザーが ticket_comments に書き込めない。管理者ユーザーでは再現しない。', NOW() - INTERVAL '2 days', NOW() - INTERVAL '8 hours'),
    (4, '問い合わせ分類の候補を増やしたい', 'Sample Software', 'resolved', 'low', 'Demo User 4', 'Product Request', 'サポートチームが使う分類に Billing と Security を追加したい。', NOW() - INTERVAL '8 days', NOW() - INTERVAL '6 days'),
    (5, '優先度の変更が監査画面に反映されない', 'Sample Healthcare', 'new', 'medium', 'Demo User 5', 'Audit', 'チケット詳細で priority を変更しても監査用ビューへの反映が遅れることがある。', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

INSERT INTO ticket_comments (id, ticket_id, author, body, created_at)
VALUES
    (1, 1, 'Demo User 1', 'ワークロード履歴を確認中。まずは集計クエリの実行時間を切り分けます。', NOW() - INTERVAL '4 days'),
    (2, 2, 'Demo User 2', '列名変更はアプリ側の表示だけでなく、エクスポート処理も確認します。', NOW() - INTERVAL '1 day'),
    (3, 3, 'Demo User 3', '権限の反映タイミングを確認するため、再現手順を整理しました。', NOW() - INTERVAL '7 hours')
ON CONFLICT DO NOTHING;

SELECT setval(pg_get_serial_sequence('tickets', 'id'), COALESCE((SELECT MAX(id) FROM tickets), 1), true);
SELECT setval(pg_get_serial_sequence('ticket_comments', 'id'), COALESCE((SELECT MAX(id) FROM ticket_comments), 1), true);
