# Databricks notebook source
# MAGIC %md
# MAGIC # AIでのデータ加工（20分）
# MAGIC
# MAGIC ここまでで学んだこと：
# MAGIC - 前半: AIがデータを**分析**してくれる（Genie）
# MAGIC - 後半前半: AIが**コード**を書いてくれる（Genie Code）
# MAGIC
# MAGIC このセッションで学ぶこと：
# MAGIC - **AIがデータ自体を加工する** — SQLからLLMを呼び出して、自由文テキストを自動処理
# MAGIC
# MAGIC ## 使う機能
# MAGIC - **ai_classify** — テキストを指定カテゴリに自動分類
# MAGIC - **ai_query** — 任意のプロンプトでLLMを呼び出して情報抽出
# MAGIC
# MAGIC ## 実行環境
# MAGIC
# MAGIC このセッションは **SQLエディター** で実施します。
# MAGIC 左メニュー **「SQLエディター」** を開いてください。
# MAGIC SQLからLLMを呼び出せる体験がより直接的に伝わります。
# MAGIC
# MAGIC ### このノートブック自体で実行する場合
# MAGIC
# MAGIC ノートブック右上の接続先を **「サーバーレス」** に変更してください。
# MAGIC
# MAGIC - ❌ `Serverless Starter Warehouse` → 一部の Python セルが動かない
# MAGIC - ✅ `サーバーレス` → 全セル実行可能

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚠️ 事前準備: サンプルデータの作成
# MAGIC
# MAGIC このハンズオンでは、ECサイト「Brick EC」のサンプルデータ（`workspace.bootcamp_osaka.*`）を使います。
# MAGIC
# MAGIC **まだ作成していない方は、先に以下のノートブックを実行してください：**
# MAGIC
# MAGIC 👉 `setup_sample_data.py`（GitHubリポジトリ内）を開いて「すべてを実行」
# MAGIC
# MAGIC 作成されるテーブル（全5つ）:
# MAGIC - `gold_users`（500行）
# MAGIC - `gold_products`（38行）
# MAGIC - `gold_transactions`（3,000行）
# MAGIC - **`gold_reviews`（1,000行）** ← このハンズオンで使用
# MAGIC - **`support_inquiries`（300行）** ← 発展問題で使用
# MAGIC
# MAGIC データが作成されていれば、以下のセルで行数が表示されます。

# COMMAND ----------

# 事前準備が完了しているか確認
result = spark.sql("""
  SELECT 'gold_reviews' AS tbl, COUNT(*) AS cnt FROM workspace.bootcamp_osaka.gold_reviews
  UNION ALL
  SELECT 'support_inquiries', COUNT(*) FROM workspace.bootcamp_osaka.support_inquiries
""")
display(result)

# COMMAND ----------

# MAGIC %md
# MAGIC # 演習1: ai_classify でレビューを感情分類
# MAGIC
# MAGIC ECサイト「Brick EC」の顧客レビューデータ（1,000件）に対して、
# MAGIC 自由文のレビュー本文をAIで自動分類します。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- レビュー本文の中身を確認
# MAGIC SELECT review_text, rating
# MAGIC FROM workspace.bootcamp_osaka.gold_reviews
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC このレビュー本文を、AIに「ポジティブ/ネガティブ/ニュートラル」で自動分類させます。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ai_classify でセンチメント分類
# MAGIC SELECT
# MAGIC   review_text,
# MAGIC   rating,
# MAGIC   ai_classify(
# MAGIC     review_text,
# MAGIC     ARRAY('ポジティブ', 'ネガティブ', 'ニュートラル')
# MAGIC   ) AS ai_sentiment
# MAGIC FROM workspace.bootcamp_osaka.gold_reviews
# MAGIC LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - SQLからLLMを呼び出せる（Python不要、外部API呼び出し不要）
# MAGIC - rating の数値と ai_sentiment が整合している
# MAGIC - **これをパイプラインに組み込めば、毎日自動でAI分類できる**
# MAGIC
# MAGIC ## 応用: 分類結果でフィルタリング

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ネガティブなレビューだけを抽出
# MAGIC SELECT *
# MAGIC FROM (
# MAGIC   SELECT
# MAGIC     review_text,
# MAGIC     rating,
# MAGIC     ai_classify(review_text, ARRAY('ポジティブ', 'ネガティブ', 'ニュートラル')) AS ai_sentiment
# MAGIC   FROM workspace.bootcamp_osaka.gold_reviews
# MAGIC   LIMIT 30
# MAGIC )
# MAGIC WHERE ai_sentiment = 'ネガティブ';

# COMMAND ----------

# MAGIC %md
# MAGIC # 演習2: ai_query でレビューから JSON 形式で情報を一括抽出
# MAGIC
# MAGIC 自由文のレビューから、**話題・感情・改善提案・緊急度の4つを JSON 形式でまとめて抽出**します。
# MAGIC
# MAGIC `responseFormat` を指定すると、LLMの出力を**決まった形の JSON** として返してくれます。
# MAGIC 自由文のままだと後で使いづらいですが、JSON なら下流のパイプラインで直接扱えます。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   review_text,
# MAGIC   ai_query(
# MAGIC     'databricks-meta-llama-3-3-70b-instruct',
# MAGIC     CONCAT('次のレビューを分析してください: ', review_text),
# MAGIC     responseFormat => 'STRUCT<result:STRUCT<
# MAGIC         topic:STRING,
# MAGIC         sentiment:STRING,
# MAGIC         improvement_suggestion:STRING,
# MAGIC         urgency:STRING>>'
# MAGIC   ) AS analysis
# MAGIC FROM workspace.bootcamp_osaka.gold_reviews
# MAGIC WHERE rating <= 3
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC **出力例:**
# MAGIC ```json
# MAGIC {"topic":"味", "sentiment":"悪い", "improvement_suggestion":"味を改善する", "urgency":"高"}
# MAGIC ```
# MAGIC
# MAGIC **確認ポイント**
# MAGIC - **1回の LLM 呼び出しで4属性をまとめて抽出** → コスト削減
# MAGIC - 出力が **JSON 構造化** されているので、ダッシュボード化・フィルタ・集計がそのままできる
# MAGIC - 従来なら Python で NLP パイプラインを組む必要があった処理が **SQL 1行** で実現

# COMMAND ----------

# MAGIC %md
# MAGIC ## JSON 出力の活用例
# MAGIC
# MAGIC 抽出した JSON からフィールドを取り出して、そのまま分析やダッシュボードに使えます。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 緊急度が「高」のレビューだけを抽出
# MAGIC WITH analyzed AS (
# MAGIC   SELECT review_text,
# MAGIC     ai_query(
# MAGIC       'databricks-meta-llama-3-3-70b-instruct',
# MAGIC       CONCAT('次のレビューを分析してください: ', review_text),
# MAGIC       responseFormat => 'STRUCT<result:STRUCT<
# MAGIC           topic:STRING,
# MAGIC           sentiment:STRING,
# MAGIC           improvement_suggestion:STRING,
# MAGIC           urgency:STRING>>'
# MAGIC     ) AS analysis
# MAGIC   FROM workspace.bootcamp_osaka.gold_reviews
# MAGIC   WHERE rating <= 3
# MAGIC   LIMIT 20
# MAGIC )
# MAGIC SELECT
# MAGIC   review_text,
# MAGIC   analysis:topic::STRING                  AS topic,
# MAGIC   analysis:improvement_suggestion::STRING AS improvement_suggestion,
# MAGIC   analysis:urgency::STRING                AS urgency
# MAGIC FROM analyzed
# MAGIC WHERE analysis:urgency::STRING = '高';

# COMMAND ----------

# MAGIC %md
# MAGIC **この形にしておけば…**
# MAGIC - `WHERE` でフィルタ: 緊急度高だけ Slack に自動通知
# MAGIC - `GROUP BY topic` で集計: 改善テーマ別ランキング
# MAGIC - ダッシュボードのデータソースにそのまま利用
# MAGIC - Jobs に組み込めば、毎朝自動で新着レビューを処理

# COMMAND ----------

# MAGIC %md
# MAGIC # 演習3（発展）: サポート問い合わせを自動振り分け
# MAGIC
# MAGIC 顧客からの問い合わせを、AIで自動的にカテゴリ分けします。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   inquiry_text,
# MAGIC   ai_classify(
# MAGIC     inquiry_text,
# MAGIC     ARRAY('配送関連', '返品交換', '支払い関連', 'アカウント関連', '商品関連', 'その他')
# MAGIC   ) AS category
# MAGIC FROM workspace.bootcamp_osaka.support_inquiries
# MAGIC LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC **これが使えると:**
# MAGIC - サポートチームの手作業が激減
# MAGIC - 問い合わせ増加にもスケール対応できる
# MAGIC - SLA改善につながる

# COMMAND ----------

# MAGIC %md
# MAGIC # 発展2: ai_query で柔軟にプロンプト指定
# MAGIC
# MAGIC 問い合わせを緊急度ごとに分類し、対応提案までAIに考えさせます。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   inquiry_text,
# MAGIC   ai_query(
# MAGIC     'databricks-meta-llama-3-3-70b-instruct',
# MAGIC     CONCAT(
# MAGIC       '次の問い合わせの緊急度を「高・中・低」で判定し、',
# MAGIC       '対応の優先度を1文で助言してください。出力形式: 緊急度: X, 助言: Y ',
# MAGIC       '問い合わせ: ', inquiry_text
# MAGIC     )
# MAGIC   ) AS ai_triage
# MAGIC FROM workspace.bootcamp_osaka.support_inquiries
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC # まとめ
# MAGIC
# MAGIC 今日の流れを振り返ると：
# MAGIC
# MAGIC | フェーズ | 内容 |
# MAGIC |---|---|
# MAGIC | **前半** | AIでデータを**分析**する（Genie / AI/BI） |
# MAGIC | **後半 Step 2-4** | 人手でデータを**加工**する（Bronze→Silver→Gold + Job）|
# MAGIC | **後半 Step 5（ここ）** | AIでデータを**加工**する（ai_classify / ai_query）|
# MAGIC
# MAGIC ## データ × AI の両輪
# MAGIC
# MAGIC - きれいなデータがあるからAIが正確に動く
# MAGIC - AIがあるからデータ整備を自動化できる
# MAGIC
# MAGIC Databricksでは、この循環が **1つのプラットフォームで完結** します。
# MAGIC
# MAGIC おつかれさまでした 🎉
