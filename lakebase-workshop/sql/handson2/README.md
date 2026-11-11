# ハンズオン Part2 Lakehouse との接続 の SQL

Part1 で作った自分のブランチとチケット管理アプリを使い、Synced Table（Lakehouse → Lakebase）と
Lakebase CDF（Lakebase → Lakehouse）で往復を組む演習の SQL です。資料の各ページにも同じ SQL を載せています。

置き換える値:

- `<カタログ>`: 演習用カタログ（default storage ではないもの。Lakebase CDF の書き出し先にも使う）
- `<名前>`: 自分の名前（英小文字と数字、先頭は英小文字）。ブランチ・プロジェクト・App・`lab_<名前>` に同じ値を使う
- `<メモした ID>`: ⑧-1 で更新したチケットの ID

同期元は全員が自分の `lab_<名前>` に作るので、ほかの人の作業に影響しません。

| ファイル | 使う場面 | 実行場所 |
|---|---|---|
| `00_lab_schema.sql` | 事前準備: 自分の UC スキーマ `lab_<名前>` と 同期元 `customer_context`（Delta CDF つき・5行） | SQLエディタ（Databricks SQL） |
| `../schema.postgres.sql`、`../seed.postgres.sql` | シードデータの投入（tickets 5件・ticket_comments 3件） | Lakebase の SQL Editor（production） |
| `01_replica_identity.postgres.sql` | シードデータの投入に続けて流す（REPLICA IDENTITY FULL） | Lakebase の SQL Editor（production） |
| `05_check_source.sql` | ⑤-1 同期元の Delta CDF と件数の確認 | SQLエディタ（Databricks SQL） |
| `06_update_source.sql` | ⑥-1 同期元の更新 | SQLエディタ（Databricks SQL） |
| `06_check_synced.postgres.sql` | ⑥-3 tickets と Synced Table の JOIN | Lakebase の SQL Editor（自分のブランチ） |
| `07_check_replica_identity.postgres.sql` | ⑦-1 REPLICA IDENTITY の確認 | Lakebase の SQL Editor（自分のブランチ） |
| `08_update_ticket.postgres.sql` | ⑧-1 アプリが動かないときの更新 | Lakebase の SQL Editor（自分のブランチ） |
| `08_history.sql` | ⑧-2 変更履歴の確認 | SQLエディタ（Databricks SQL） |
| `08_aggregate.sql` | ⑧-4 履歴の畳み込みと 顧客属性との集計 | SQLエディタ（Databricks SQL） |
| `09_cleanup.sql` | 片付け: 自分の UC スキーマ | SQLエディタ（Databricks SQL） |

アプリは Synced Table（`lab_<名前>.customer_context_synced`）を自動で見つけて、チケット詳細に顧客情報を出します。
Part1 で Deploy したアプリのままでよく、Deploy し直す必要はありません。
