# Databricks notebook source
# MAGIC %md
# MAGIC # Databricks データエンジニアリング ハンズオン
# MAGIC
# MAGIC このノートブックは、Databricksの様々なツールを巡る**ツアーガイド**です。
# MAGIC 左メニューの各機能を順番に触っていただきます。
# MAGIC
# MAGIC ## 全体の流れ（約40分）
# MAGIC
# MAGIC | | 使うツール | 時間 | 内容 |
# MAGIC |---|---|---|---|
# MAGIC | Step 1 | **ノートブック**（ここ） | 20分 | Bronze → Silver を作る |
# MAGIC | 休憩 | — | 15分 | |
# MAGIC | Step 2 | **データエンジニアリング** | 10分 | Lakeflow Jobs で自動化 |
# MAGIC | Step 3 | **カタログ + Genie** | 10分 | Gold作成・結果確認 |
# MAGIC | Step 4 | **SQLエディター** | 5分 | Brick EC を SQL で分析 |
# MAGIC
# MAGIC ## 進め方
# MAGIC - 各ステップの指示に従って、指定のツールを左メニューから開きます
# MAGIC - 完了したらこのノートブックに戻ってきて次のステップへ
# MAGIC - **Genie Code** を積極的に使ってください（`Cmd+I` / `Ctrl+I` で起動）
# MAGIC
# MAGIC ## ⚠️ 事前設定: コンピュートの選択
# MAGIC
# MAGIC **ノートブック右上の接続先を「サーバーレス」に変更してください**。
# MAGIC
# MAGIC - ❌ `Serverless Starter Warehouse`（SQLウェアハウス）→ Python が動かない
# MAGIC - ✅ `サーバーレス`（ノートブック用コンピュート）→ Python も SQL も動く

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 1: Bronze → Silver を作る（20分）
# MAGIC
# MAGIC ここでは、生データを段階的に整備するメダリオンアーキテクチャを構築します。
# MAGIC
# MAGIC **💡 Genie Code を活用しましょう**
# MAGIC コードセルで `Cmd+I` を押すと Genie Code が起動し、日本語の指示からコードを生成してくれます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-1. 作業用スキーマを UI で作成
# MAGIC
# MAGIC **ここはノートブックを離れて、カタログエクスプローラーで作業します。**
# MAGIC
# MAGIC 1. 左メニューから **「カタログ」** をクリック
# MAGIC 2. `workspace` カタログを選択
# MAGIC 3. 右上の **「作成」→「スキーマ」** をクリック
# MAGIC 4. スキーマ名を入力（例: `bc_yourname`。他の参加者と被らない名前）
# MAGIC 5. **「作成」** をクリック
# MAGIC
# MAGIC → スキーマが作成されたら、次のセルで自分のスキーマ名を入力してください。

# COMMAND ----------

# ↓ 自分が作成したスキーマ名を入力してください
my_schema = "bc_yourname"  # ← 変更

spark.sql(f"USE CATALOG workspace")
spark.sql(f"USE SCHEMA {my_schema}")
print(f"作業スキーマ: workspace.{my_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-2. Volume を UI で作成してサンプルデータをアップロード
# MAGIC
# MAGIC ### (a) Volume を作成
# MAGIC
# MAGIC 1. カタログエクスプローラーで、作成したスキーマを開く
# MAGIC 2. スキーマの画面で右上の **「作成」→「ボリューム」** をクリック
# MAGIC 3. ボリューム名: `files` と入力
# MAGIC 4. タイプ: **マネージドボリューム** を選択
# MAGIC 5. **「作成」** をクリック
# MAGIC
# MAGIC ### (b) サンプル CSV をアップロード
# MAGIC
# MAGIC 1. 作成した `files` ボリュームを開く
# MAGIC 2. 右上の **「このボリュームにアップロード」** をクリック
# MAGIC 3. GitHub リポジトリからクローンした `Bootcamp_osaka_second half_data/iot_data.csv` を選択してアップロード
# MAGIC 4. ファイルがアップロードされたことを確認
# MAGIC
# MAGIC ### (c) パスを確認
# MAGIC
# MAGIC アップロード後、ファイルのパスは以下になります：
# MAGIC ```
# MAGIC /Volumes/workspace/<自分のスキーマ>/files/iot_data.csv
# MAGIC ```

# COMMAND ----------

# Volume のパスを設定して中身を確認
volume_path = f"/Volumes/workspace/{my_schema}/files"
csv_path = f"{volume_path}/iot_data.csv"

df = spark.read.format("csv").option("header", "true").load(csv_path)
print(f"読み込み件数: {df.count()}行")
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-3. Bronze層を作る（COPY INTO）
# MAGIC
# MAGIC **💡 Genie Code に挑戦**
# MAGIC 次のセルで `Cmd+I` を押して、以下のように指示してみてください：
# MAGIC
# MAGIC > 「{volume_path}/iot_data.csv を COPY INTO で iot_bronze テーブルに取り込んで。全カラムSTRING型、ingestion_timeカラム追加」
# MAGIC
# MAGIC 生成されたコードが微妙に違っても、下の SQL を実行すればOKです。

# COMMAND ----------

# 既存テーブルがあればスキーマ変更に対応するため削除
spark.sql(f"DROP TABLE IF EXISTS workspace.{my_schema}.iot_bronze")

spark.sql(f"""
CREATE TABLE workspace.{my_schema}.iot_bronze (
  device_id STRING,
  device_type STRING,
  location STRING,
  timestamp STRING,
  temperature STRING,
  humidity STRING,
  status STRING,
  ingestion_time TIMESTAMP
)
""")

spark.sql(f"""
COPY INTO workspace.{my_schema}.iot_bronze
FROM (
  SELECT *, current_timestamp() AS ingestion_time
  FROM '{volume_path}/iot_data.csv'
)
FILEFORMAT = CSV
FORMAT_OPTIONS ('header' = 'true')
""")

display(spark.sql(f"SELECT * FROM workspace.{my_schema}.iot_bronze LIMIT 10"))

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - 全カラムが STRING 型で入っている
# MAGIC - 一部セルが null、空文字、"N/A" のまま入っている
# MAGIC - ingestion_time にタイムスタンプが付いている
# MAGIC
# MAGIC → これが **Bronze層**（生データをそのまま保持）

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-4. Silver層を作る（クレンジング + 型変換）
# MAGIC
# MAGIC **💡 Genie Code に挑戦**
# MAGIC > 「iot_bronze から型変換（timestampをTIMESTAMP、temperature/humidityをDOUBLE）とNULL処理（空文字と"N/A"をNULLに）をして iot_silver を作って」
# MAGIC
# MAGIC **ℹ️ Genie Code が `CREATE OR REPLACE TABLE` に警告を出すことがあります**
# MAGIC
# MAGIC Genie Code は破壊的操作に対して安全性レビューを行います（**本番で便利な機能**）。
# MAGIC ただし今回は：
# MAGIC - ハンズオン環境でデータを作り直す前提
# MAGIC - Delta Lake は `CREATE OR REPLACE` でも**履歴を保持**するため Time Travel 可能
# MAGIC
# MAGIC → 今回は警告が出ても実行してOKです

# COMMAND ----------

# ハンズオン環境のため CREATE OR REPLACE を使用
# 注: Delta Lake は履歴を保持するため、Time Travel で過去データに戻れます
# 本番環境では INSERT INTO / MERGE の使用を推奨
spark.sql(f"""
CREATE OR REPLACE TABLE workspace.{my_schema}.iot_silver AS
SELECT
  device_id,
  device_type,
  location,
  CAST(timestamp AS TIMESTAMP) AS timestamp,
  CAST(NULLIF(NULLIF(temperature, ''), 'N/A') AS DOUBLE) AS temperature,
  CAST(NULLIF(NULLIF(humidity, ''), 'N/A') AS DOUBLE) AS humidity,
  NULLIF(NULLIF(status, ''), 'N/A') AS status,
  ingestion_time
FROM workspace.{my_schema}.iot_bronze
WHERE temperature != '999'
""")

display(spark.sql(f"SELECT * FROM workspace.{my_schema}.iot_silver LIMIT 10"))

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - temperature, humidity が **DOUBLE型** になっている
# MAGIC - 空文字や "N/A" が **NULL** に変換されている
# MAGIC - timestamp が **TIMESTAMP型** になっている
# MAGIC
# MAGIC → これが **Silver層**（信頼できるデータ）

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-5. Delta Lake の Time Travel を体験
# MAGIC
# MAGIC ### Time Travel とは？
# MAGIC
# MAGIC Delta Lake は、テーブルに対する**すべての変更（INSERT / UPDATE / DELETE）を履歴として保持**します。
# MAGIC そのため、**過去の任意の時点のデータ**を参照できます。
# MAGIC
# MAGIC ```
# MAGIC バージョン 0 : テーブル作成直後の状態（UPDATE前）
# MAGIC バージョン 1 : UPDATEを実行した後の状態
# MAGIC   ...
# MAGIC ```
# MAGIC
# MAGIC ### 何に使えるか
# MAGIC
# MAGIC - **誤操作からの復旧**: 間違えて UPDATE/DELETE した時、過去の状態に戻せる
# MAGIC - **監査**: 「先月末時点のデータはどうだった？」を再現できる
# MAGIC - **デバッグ**: 問題発生前のデータと比較して原因調査ができる
# MAGIC - **再現可能な分析**: 特定の時点のデータで過去分析を再現
# MAGIC
# MAGIC ### このハンズオンで体験する流れ
# MAGIC
# MAGIC 1. **今の状態（バージョン1）** — DEV001 の status を `maintenance` に UPDATE
# MAGIC 2. **過去の状態（バージョン0）** — UPDATE前の `normal` をそのまま参照
# MAGIC
# MAGIC → **UPDATE したのに、過去のデータも残っている**ことを確認します

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: DEV001 の status を更新する
# MAGIC
# MAGIC 「DEV001 は実は今メンテナンス中だった」という想定で status を更新します。

# COMMAND ----------

spark.sql(f"""
UPDATE workspace.{my_schema}.iot_silver
SET status = 'maintenance'
WHERE device_id = 'DEV001'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: 現在の状態を確認（UPDATE 後）
# MAGIC
# MAGIC DEV001 の status が `maintenance` になっているはずです。

# COMMAND ----------

display(spark.sql(f"""
SELECT device_id, status FROM workspace.{my_schema}.iot_silver
WHERE device_id = 'DEV001' LIMIT 5
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: 過去の状態を確認（UPDATE 前）
# MAGIC
# MAGIC `VERSION AS OF 0` をつけると、テーブル作成直後の状態にアクセスできます。
# MAGIC DEV001 の status は元の値（`normal` など）のままのはずです。

# COMMAND ----------

display(spark.sql(f"""
SELECT device_id, status FROM workspace.{my_schema}.iot_silver VERSION AS OF 0
WHERE device_id = 'DEV001' LIMIT 5
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 確認ポイント
# MAGIC
# MAGIC | クエリ | 結果 |
# MAGIC |---|---|
# MAGIC | 通常の SELECT（バージョン1 = 現在） | status が `maintenance` |
# MAGIC | `VERSION AS OF 0`（バージョン0 = UPDATE前） | status は元の値（normal など） |
# MAGIC
# MAGIC **→ UPDATE してもデータは消えていない。Delta Lake は履歴を全て保持している**
# MAGIC
# MAGIC ### おまけ: 履歴を見る
# MAGIC
# MAGIC どんな変更がいつ行われたか、以下で確認できます。

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY workspace.{my_schema}.iot_silver"))

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # 🍵 ここで 15分休憩
# MAGIC
# MAGIC ---

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 2: Lakeflow Jobs で自動化（10分）
# MAGIC
# MAGIC ここから**ノートブックを離れます**。
# MAGIC
# MAGIC ## 2-1. ジョブ作成画面を開く
# MAGIC
# MAGIC 1. 左メニューから **「データエンジニアリング」** → **「ジョブ」** をクリック
# MAGIC 2. 右上の **「作成」→「ジョブ」**（Create → Job）をクリック
# MAGIC
# MAGIC ## 2-2. ジョブ名を設定
# MAGIC
# MAGIC - ジョブ名: `DE_Pipeline_<自分のユーザー名>`
# MAGIC
# MAGIC ## 2-3. タスク1を追加：Bronze取込
# MAGIC
# MAGIC | 項目 | 値 |
# MAGIC |---|---|
# MAGIC | タスク名 | `bronze_ingestion` |
# MAGIC | タスクの種類 | ノートブック |
# MAGIC | ソース | Workspace |
# MAGIC | パス | このノートブック（00_main）を選択 |
# MAGIC | コンピュート | サーバーレス |
# MAGIC
# MAGIC ## 2-4. タスク2を追加：Silver変換
# MAGIC
# MAGIC 「+ タスクを追加」をクリック
# MAGIC
# MAGIC | 項目 | 値 |
# MAGIC |---|---|
# MAGIC | タスク名 | `silver_transform` |
# MAGIC | 依存先 | `bronze_ingestion` を選択（これで直列実行される）|
# MAGIC | タスクの種類 | ノートブック |
# MAGIC | ソース | Workspace |
# MAGIC | パス | このノートブック（00_main）を選択 |
# MAGIC
# MAGIC ## 2-5. 手動実行してみる
# MAGIC
# MAGIC 右上の **「今すぐ実行」** をクリック。
# MAGIC タスクが緑のチェックマークになれば成功です。
# MAGIC
# MAGIC ## 2-6. （余裕があれば）スケジュールを追加
# MAGIC
# MAGIC 「トリガーを追加」→「スケジュール」で、毎日実行などを設定できます。
# MAGIC
# MAGIC **⏎ このノートブックに戻って、Step 4 へ進みます**

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 3: カタログ + Genie で結果を確認（10分）
# MAGIC
# MAGIC ## 3-1. カタログエクスプローラーで自分のテーブルを見る
# MAGIC
# MAGIC 1. 左メニュー **「カタログ」** をクリック
# MAGIC 2. `workspace` > `my_workspace`（または自分のスキーマ） を展開
# MAGIC 3. `iot_silver` をクリック
# MAGIC 4. 以下のタブを確認：
# MAGIC    - **概要**: カラム定義
# MAGIC    - **サンプルデータ**: 中身のデータ
# MAGIC    - **履歴**: Time Travel で作成した全バージョンが見える
# MAGIC
# MAGIC ## 3-2. Gold層を作る
# MAGIC
# MAGIC 以下のセルを実行して、デバイスごとの集計 Gold テーブルを作成します。

# COMMAND ----------

# デバイスタイプ × 地域 で集計（ビジネス目線の Gold テーブル）
# CREATE OR REPLACE は Genie Code が警告することがありますが、Delta は履歴を保持するため安全です
spark.sql(f"""
CREATE OR REPLACE TABLE workspace.{my_schema}.iot_gold AS
SELECT
  device_type,
  location,
  COUNT(DISTINCT device_id) AS device_count,
  ROUND(AVG(temperature), 1) AS avg_temperature,
  ROUND(AVG(humidity), 1) AS avg_humidity,
  COUNT(*) AS reading_count,
  SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END) AS critical_count,
  SUM(CASE WHEN status = 'warning'  THEN 1 ELSE 0 END) AS warning_count
FROM workspace.{my_schema}.iot_silver
GROUP BY device_type, location
ORDER BY critical_count DESC, warning_count DESC
""")

display(spark.sql(f"SELECT * FROM workspace.{my_schema}.iot_gold"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3-3. Genie で自分の Gold テーブルに質問
# MAGIC
# MAGIC 前半で体験した Genie に、自分で作ったテーブルを使わせてみます。
# MAGIC
# MAGIC 1. 左メニューから **「Genie」** をクリック
# MAGIC 2. 右上 **「新規」** → Genieスペース作成
# MAGIC 3. カタログ: `workspace`、スキーマ: `my_workspace`（自分のスキーマ）
# MAGIC 4. `iot_gold` テーブルを選択して作成
# MAGIC 5. （日本語で回答させたい場合は設定 > 指示に「日本語で回答して」を追加）
# MAGIC
# MAGIC 試しに以下を質問してみてください：
# MAGIC
# MAGIC > 「一番平均温度が高いデバイスは？」
# MAGIC
# MAGIC > 「各デバイスの湿度と温度の関係を棒グラフで見せて」
# MAGIC
# MAGIC **🎉 前半で体験したGenieの世界が、自分で作ったデータで再現できました！**

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 4: SQLエディターで自分のデータを分析
# MAGIC
# MAGIC 最後に、自分で作った IoT の Gold テーブルを SQLエディターでも触ってみます。
# MAGIC ノートブック以外に **SQLエディター** というツールもあることを体験します。
# MAGIC
# MAGIC ## 4-1. SQLエディターを開く
# MAGIC
# MAGIC 左メニューから **「SQLエディター」** をクリックしてください。
# MAGIC
# MAGIC ## 4-2. SQLで分析してみる
# MAGIC
# MAGIC 以下のクエリをコピペして実行してください（`Shift + Enter`）。
# MAGIC **`<my_schema>` は自分のスキーマ名に置き換えてください**（例: `bc_yourname`）。
# MAGIC
# MAGIC ### 例1: Gold テーブルの中身を見る
# MAGIC ```sql
# MAGIC SELECT * FROM workspace.<my_schema>.iot_gold;
# MAGIC ```
# MAGIC
# MAGIC ### 例2: デバイスタイプ別の合計読み取り件数
# MAGIC ```sql
# MAGIC SELECT
# MAGIC   device_type,
# MAGIC   SUM(reading_count) AS total_readings,
# MAGIC   SUM(critical_count) AS total_critical
# MAGIC FROM workspace.<my_schema>.iot_gold
# MAGIC GROUP BY device_type
# MAGIC ORDER BY total_critical DESC;
# MAGIC ```
# MAGIC
# MAGIC ### 例3: critical が多い組み合わせ Top 3
# MAGIC ```sql
# MAGIC SELECT
# MAGIC   device_type,
# MAGIC   location,
# MAGIC   critical_count
# MAGIC FROM workspace.<my_schema>.iot_gold
# MAGIC ORDER BY critical_count DESC
# MAGIC LIMIT 3;
# MAGIC ```
# MAGIC
# MAGIC ## 4-3. Genie Code を SQLエディターで使う（任意）
# MAGIC
# MAGIC SQLエディターで `Cmd+I`（Mac）/ `Ctrl+I`（Win）を押すと Genie Code が起動します。
# MAGIC 自然言語で指示すると SQL を生成してくれます：
# MAGIC
# MAGIC > 「Silver テーブルから、1時間ごとの平均温度を計算して」
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC # ここまでがメインハンズオン
# MAGIC
# MAGIC 次は **AIでのデータ加工** に進みます。
# MAGIC `01_ai_data_processing.py` を開いてください。
# MAGIC
# MAGIC ※ AIデータ加工では別のサンプルデータ（Brick EC）を使います。
# MAGIC `setup_sample_data.py` を先に実行しておいてください。
