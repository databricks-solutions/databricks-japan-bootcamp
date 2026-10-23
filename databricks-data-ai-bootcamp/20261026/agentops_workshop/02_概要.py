# Databricks notebook source
# MAGIC %md
# MAGIC # 02. 概要: このハンズオンで作るエージェントアプリ
# MAGIC
# MAGIC このハンズオンのシナリオと、作るものの全体像をまとめています。`01_準備` を実行したあと、AI Search の立ち上げを待つあいだに読みます（図は、セルを実行すると表示されます）。
# MAGIC
# MAGIC | # | 内容 |
# MAGIC |---|---|
# MAGIC | 1 | 想定シナリオ |
# MAGIC | 2 | 作るエージェント |
# MAGIC | 3 | 使うデータ |
# MAGIC | 4 | アーキテクチャ |
# MAGIC | 5 | ハンズオンの流れ（AgentOps のライフサイクル） |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 想定シナリオ
# MAGIC 家電メーカー「ブリックス電機」（架空）のコールセンターで、**修理受付のオペレーターを支援するエージェント**を作ります。
# MAGIC
# MAGIC オペレーターが、お客様から聞いた内容（製造番号・購入日・症状）を文章のまま入れると、エージェントが製品情報・取扱説明書・サービス技術情報・過去の対応を調べて、**根拠付きの回答案**と**次の対応**（一次対処の案内・修理受付・無償点検の手配など）を返します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 作るエージェント
# MAGIC オペレーターが、お客様から聞いた内容を文章のまま入れると、エージェントがツールを使って調べ、回答案を作ります。

# COMMAND ----------

# 図の HTML は diagrams.py にある
from diagrams import agent_flow_html, architecture_html, er_html

displayHTML(agent_flow_html())

# COMMAND ----------

# MAGIC %md
# MAGIC **ツールを使う流れ（想定）**
# MAGIC
# MAGIC ツールを呼ぶ順番や回数は、エージェント（Claude）が相談の内容とツールの結果を見て決めます。想定している流れは次のとおりです。
# MAGIC
# MAGIC | # | すること | 使うツール | 例（上の相談の場合） |
# MAGIC |---|---|---|---|
# MAGIC | 1 | 相談の文章から、製造番号・購入日・症状を読み取る | ― | 製造番号 RC5-2604B-00871、購入日 2026-08-03、症状「炊いている途中で電源が切れる」 |
# MAGIC | 2 | 製造番号から、型番・ロット・製造月・保証の状態を確かめる | ① `get_product_info` | 型番 RC-500、ロット RC5-2604B、保証の状態 |
# MAGIC | 3 | その型番の取扱説明書・サービス技術情報から、症状への対処や、無償点検の対象かを調べる | ② `search_documents` | 「RC-500 炊飯中に電源が切れる」などで検索 |
# MAGIC | 4 | 必要に応じて、似た症状の過去の対応を参考にする | ③ `search_past_cases` | 同じ型番・症状の過去の対応 |
# MAGIC | 5 | 調べた結果をもとに、回答案・次の対応・根拠をまとめる | ― | 「返すもの」の形式で返す |
# MAGIC
# MAGIC 回答案の「次の対応」は、**一次対処で様子を見る／使用を中止して修理受付／無償点検を手配／使用を中止して至急対応／担当者に確認** のどれか1つです。
# MAGIC
# MAGIC エージェントが正しく対応できるかを、次の4種類の相談で確かめます（`05_評価`・`06_改善`）。
# MAGIC
# MAGIC | 相談の種類 | 見たいこと |
# MAGIC |---|---|
# MAGIC | 無償点検の対象 | 対象のロットかを確かめて、点検の案内が漏れないか |
# MAGIC | 似た型番 | その型番の説明書で、正しい手順を案内できるか |
# MAGIC | 修理がいらない | 使い方の案内で解決できるか |
# MAGIC | 安全に関わる症状 | まず使用の中止を案内できるか |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 使うデータ
# MAGIC `01_準備` で、同梱の CSV からテーブルを作り、PDF を Volume に置きました。製造番号の先頭がロット番号で、ロットから型番・製造月がわかります。

# COMMAND ----------

displayHTML(er_html())

# COMMAND ----------

# MAGIC %md
# MAGIC **テーブルのサンプル**
# MAGIC
# MAGIC `products`（製品）
# MAGIC
# MAGIC | model_no | product_name | category | warranty_months |
# MAGIC |---|---|---|---|
# MAGIC | RC-500 | IH炊飯器 RC-500（5.5合） | 炊飯器 | 12 |
# MAGIC | RC-550 | 圧力IH炊飯器 RC-550（5.5合） | 炊飯器 | 12 |
# MAGIC | KT-200 | 電気ケトル KT-200（1.0L） | 電気ケトル | 12 |
# MAGIC
# MAGIC `production_lots`（製造ロット）
# MAGIC
# MAGIC | lot_no | model_no | factory | production_month |
# MAGIC |---|---|---|---|
# MAGIC | RC5-2604A | RC-500 | 新潟工場 | 2026-04-01 |
# MAGIC | RC5-2604B | RC-500 | 新潟工場 | 2026-04-01 |
# MAGIC
# MAGIC `repair_requests`（過去の修理履歴）。対応メモには、お客様の氏名・電話番号・住所が書かれています（エージェントに渡す前にマスクします）。
# MAGIC
# MAGIC | request_id | model_no | serial_no | symptom_category | result_category | operator_memo |
# MAGIC |---|---|---|---|---|---|
# MAGIC | R-2607-09140 | FN-210 | FN2-2602C-33590 | 異音 | 持込修理 | 木村 誠様（080-6950-2729）より入電。リビング扇風機 FN-210、羽根が回るとカラカラ音がする。… |
# MAGIC | R-2607-09141 | VC-700 | VC7-2508C-04938 | 電源が入らない | 持込修理 | Web受付。井上 大輔様（k.tanaka97@example.com）。コードレス掃除機 VC-700、スイッチを押しても動かない。… |
# MAGIC
# MAGIC **文書（PDF・Volume）**
# MAGIC
# MAGIC | 文書 | 数 | 内容 |
# MAGIC |---|---|---|
# MAGIC | 取扱説明書 | 製品ごとに1本（10本） | 使い方・お手入れ・トラブル対処の表・エラー表示の一覧 |
# MAGIC | サービス技術情報 | 6本 | 修理担当者・コールセンター向けの通達。既知の不具合と対処、無償点検の対象 |
# MAGIC | 保証規定・修理料金表 | 1本 | 保証の条件、修理料金の目安 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. アーキテクチャ
# MAGIC データからエージェント・評価・アプリ・トレースまで、Databricks の中で完結します。**ノートブックで評価したエージェントのコードを、そのままアプリとしてデプロイします。**

# COMMAND ----------

displayHTML(architecture_html())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. ハンズオンの流れ（AgentOps のライフサイクル）
# MAGIC エージェントを「作る」より、「品質を確かめて、届けて、見守る」ことに時間を使います。
# MAGIC
# MAGIC | ステップ | ノートブック | やること | 使う機能 | 時間 |
# MAGIC |---|---|---|---|---|
# MAGIC | 準備 | `00_設定`・`01_準備` | AI Search の用意、データの配置、モデルの確認 | ― | 約5分 |
# MAGIC | 概要 | `02_概要` | シナリオと全体像（このノートブック） | ― | 約20分 |
# MAGIC | データ準備 | `03_データパイプライン` | PDF・テーブルを、エージェントが検索できる形にする | AI関数・AI Search・UC関数 | 約12分 |
# MAGIC | エージェント | `04_エージェント` | エージェントのコードを読み、1件動かしてトレースを見る | LangGraph・MCP・MLflow Tracing | 約6分 |
# MAGIC | オフライン評価 | `05_評価` | 初版を評価し、落ちたケースの理由とトレースを見る。Genie Code で改善案を出す | MLflow の評価・Genie Code | 約10分 |
# MAGIC | 改善・再評価 | `06_改善` | 改善版を同じ評価データで評価し、初版と比べる | MLflow の評価 | 約10分 |
# MAGIC | デプロイ・監視 | `07_デプロイと監視` | 改善版をチャット画面付きのアプリにして、本番のトレースを見る | Databricks Apps・MLflow Tracing | 約12分 |
# MAGIC
# MAGIC 終わったら `99_クリーンアップ` で、自分が作ったものを削除します。
# MAGIC
# MAGIC 次は `03_データパイプライン` に進みます。
