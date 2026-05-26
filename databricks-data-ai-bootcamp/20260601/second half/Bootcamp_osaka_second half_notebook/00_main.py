# Databricks notebook source
# MAGIC %md
# MAGIC # Databricks データエンジニアリング ハンズオン
# MAGIC
# MAGIC このノートブックは、Databricksの様々なツールを巡る**ツアーガイド**です。
# MAGIC 左メニューの各機能を順番に触っていただきます。
# MAGIC
# MAGIC ## 全体の流れ（DE ハンズオン①②: 約 40 分 + 休憩 15 分）
# MAGIC
# MAGIC | | 使うツール | 時間 | 内容 |
# MAGIC |---|---|---|---|
# MAGIC | **DEハンズオン①** | | | |
# MAGIC | Step 1 | **ノートブック**（ここ） | 23分 | **Bronze → Silver → Gold + メトリックビュー + Time Travel 体験** |
# MAGIC | 休憩 | — | 15分 | |
# MAGIC | **DEハンズオン②** | | | |
# MAGIC | Step 2 | **データエンジニアリング** | 12分 | **Lakeflow Jobs で 3 タスク直列パイプライン化** |
# MAGIC | Step 3 | **カタログ + Genie** | 5分 | Gold テーブルを Genie で確認 |
# MAGIC | Step 4 | **SQLエディター** | 3分 | Gold テーブルを SQL で分析 |
# MAGIC
# MAGIC ## 進め方
# MAGIC - 各ステップの指示に従って、指定のツールを左メニューから開きます
# MAGIC - 完了したらこのノートブックに戻ってきて次のステップへ
# MAGIC - **Genie Code** を積極的に使ってください（`Cmd+I` / `Ctrl+I` で起動。動かないときは虹色ランプアイコン）
# MAGIC
# MAGIC ## このノートブックで使うテーブル / ビュー
# MAGIC
# MAGIC | 名前 | 種類 | 由来 |
# MAGIC |---|---|---|
# MAGIC | `workspace.bootcamp_osaka.iot_data` | テーブル | UI でアップロードした生データ（事前準備で作成） |
# MAGIC | `workspace.bootcamp_osaka.iot_bronze` | テーブル | Step 1-2 で作成（生データ + 取込時刻）|
# MAGIC | `workspace.bootcamp_osaka.iot_silver` | テーブル | Step 1-3 で作成（型変換 + NULL 処理）|
# MAGIC | `workspace.bootcamp_osaka.iot_gold` | テーブル | Step 1-5 で作成（集計）|
# MAGIC | `workspace.bootcamp_osaka.iot_metrics` | メトリックビュー | Step 1-6 で作成（業務指標の定義） |
# MAGIC
# MAGIC ## ⚠️ 事前設定: コンピュートの選択
# MAGIC
# MAGIC **ノートブック右上の接続先を「サーバーレス」に変更してください**。
# MAGIC
# MAGIC - ❌ `Serverless Starter Warehouse`（SQLウェアハウス）→ Python が動かない
# MAGIC - ✅ `Serverless`（ノートブック用コンピュート）→ Python も SQL も動く

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 1: Bronze → Silver → Gold + メトリックビュー を作る（23分）
# MAGIC
# MAGIC ここでは、生データを段階的に整備するメダリオンアーキテクチャを構築します。
# MAGIC
# MAGIC **💡 Genie Code を活用しましょう**
# MAGIC コードセルで **`Cmd+I`（Mac）/ `Ctrl+I`（Windows）** を押すと Genie Code が起動し、日本語の指示からコードを生成してくれます。
# MAGIC
# MAGIC ショートカットがうまく動かない場合は、コードセル右上の **虹色ランプアイコン** から起動してください。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-1. 事前準備：データの登録
# MAGIC
# MAGIC データの加工処理を行う前に、データをカタログに登録します
# MAGIC
# MAGIC | # | やること | スライド |
# MAGIC |---|---|---|
# MAGIC | 1 | カタログ `workspace` 配下に **スキーマ `bootcamp_osaka`** を UI で作成
# MAGIC | 2 | スキーマに CSVファイル をアップロードして **テーブル を３つ作成
# MAGIC
# MAGIC
# MAGIC ****

# COMMAND ----------

# workspace カタログに bootcamp_osaka スキーマを作成
spark.sql("CREATE SCHEMA IF NOT EXISTS workspace.bootcamp_osaka")

# COMMAND ----------

# DBTITLE 1,3つのCSVファイルをテーブルとして登録
# Bootcamp_osaka_second half_data フォルダ内の3つのCSVファイルを
# workspace.bootcamp_osaka スキーマにテーブルとして登録します

import pandas as pd

# ノートブックの現在のパスを取得
notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
print(f"ノートブックパス: {notebook_path}")

# データフォルダへのパス計算
base_path = notebook_path.rsplit('/', 2)[0]
data_path = f"{base_path}/Bootcamp_osaka_second half_data"

print(f"データフォルダパス: {data_path}")

# スキーマ設定
spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA bootcamp_osaka")

# 3つのCSVファイルを読み込んでテーブル作成
files_to_load = [
    ("iot_data.csv", "iot_data"),
    ("gold_reviews.csv", "gold_reviews"),
    ("support_inquiries.csv", "support_inquiries")
]

for csv_file, table_name in files_to_load:
    # Workspaceファイルをpandasで読み込んでSpark DataFrameに変換
    file_path = f"/Workspace{data_path}/{csv_file}"
    print(f"\n読み込み中: {file_path}")
    
    # pandasでCSVを読み込み
    pdf = pd.read_csv(file_path)
    
    # Spark DataFrameに変換
    df = spark.createDataFrame(pdf)
    
    # Deltaテーブルとして保存
    df.write.format("delta") \
        .mode("overwrite") \
        .saveAsTable(f"workspace.bootcamp_osaka.{table_name}")
    
    row_count = df.count()
    print(f"✓ テーブル workspace.bootcamp_osaka.{table_name} を作成しました ({row_count}行)")

print("\n全テーブルの登録が完了しました!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-2. Bronze層を作る（取込メタデータの付与）
# MAGIC
# MAGIC アップロードした `iot_data` をそのまま使ってもいいのですが、
# MAGIC **「いつ取り込んだか」** という情報を残しておくと、運用上のトレース性が上がります。
# MAGIC
# MAGIC `iot_data` をベースに、**`ingestion_time`（取込時刻）を付与した `iot_bronze`** を作成します。
# MAGIC これが Bronze 層（生データに最低限のメタデータを付けたもの）です。
# MAGIC
# MAGIC **💡 Genie Code に挑戦**
# MAGIC 次のセルで **`Cmd+I`（Mac）/ `Ctrl+I`（Windows）** または **虹色ランプアイコン** で Genie Code を起動し、以下のように指示してみてください：
# MAGIC
# MAGIC > 「`workspace.bootcamp_osaka.iot_data` をベースに、`ingestion_time`（現在時刻）を追加して `workspace.bootcamp_osaka.iot_bronze` テーブルを作成して」
# MAGIC
# MAGIC 生成されたコードが微妙に違っても、下の SQL を実行すればOKです。

# COMMAND ----------

# 作業コンテキストを設定 + iot_data テーブルが存在するか確認
spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA bootcamp_osaka")

result = spark.sql("SELECT COUNT(*) AS row_count FROM workspace.bootcamp_osaka.iot_data")
display(result)
display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_data LIMIT 5"))

# COMMAND ----------

# DBTITLE 1,データフォルダの存在確認
# データフォルダ内のファイルをリストアップ
import os

notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
base_path = notebook_path.rsplit('/', 2)[0]
data_path = f"/Workspace{base_path}/Bootcamp_osaka_second half_data"

print(f"データフォルダ: {data_path}")
print("\nファイル一覧:")

if os.path.exists(data_path):
    files = os.listdir(data_path)
    for f in sorted(files):
        full_path = os.path.join(data_path, f)
        if os.path.isfile(full_path):
            print(f"  - {f}")
else:
    print("フォルダが存在しません")

# COMMAND ----------

# Bronze 層作成（iot_data + ingestion_time）
spark.sql("""
CREATE OR REPLACE TABLE workspace.bootcamp_osaka.iot_bronze AS
SELECT
  *,
  current_timestamp() AS ingestion_time
FROM workspace.bootcamp_osaka.iot_data
""")

display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_bronze LIMIT 10"))

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - 元の `iot_data` の全カラムがそのまま入っている
# MAGIC - 一部セルが null、空文字、"N/A" のまま入っている（生データ保持）
# MAGIC - `ingestion_time` に取込時刻が付いている
# MAGIC
# MAGIC → これが **Bronze 層**（生データ + 取込メタデータ）

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-3. Silver層を作る（クレンジング + 型変換）
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
#
# TRY_CAST を使用して不正値（''、'N/A'、想定外の文字列など）を NULL に自動変換
# （Spark ANSI モードでは CAST が厳格になり、'' → DOUBLE がエラーになるため）
spark.sql("""
CREATE OR REPLACE TABLE workspace.bootcamp_osaka.iot_silver AS
SELECT
  device_id,
  device_type,
  location,
  TRY_CAST(timestamp AS TIMESTAMP) AS timestamp,
  TRY_CAST(temperature AS DOUBLE) AS temperature,
  TRY_CAST(humidity AS DOUBLE) AS humidity,
  CASE WHEN status IN ('', 'N/A') THEN NULL ELSE status END AS status,
  ingestion_time
FROM workspace.bootcamp_osaka.iot_bronze
WHERE TRY_CAST(temperature AS DOUBLE) IS DISTINCT FROM 999  -- 異常値 999 を除外（NULL は残す）
""")

display(spark.sql(f"SELECT * FROM workspace.bootcamp_osaka.iot_silver LIMIT 10"))

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
# MAGIC ## 1-4. Delta Lake の Time Travel を体験
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
UPDATE workspace.bootcamp_osaka.iot_silver
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
SELECT device_id, status FROM workspace.bootcamp_osaka.iot_silver
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
SELECT device_id, status FROM workspace.bootcamp_osaka.iot_silver VERSION AS OF 0
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

display(spark.sql(f"DESCRIBE HISTORY workspace.bootcamp_osaka.iot_silver"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-5. Gold層を作る（ビジネス指標の集計）
# MAGIC
# MAGIC 最後に、ビジネスで使える形に集計した **Gold 層** を作成します。
# MAGIC `device_type` × `location` ごとに、デバイス数・平均気温/湿度・読み取り件数・異常件数を集計します。
# MAGIC
# MAGIC **💡 Genie Code に挑戦**
# MAGIC > 「`workspace.bootcamp_osaka.iot_silver` から `device_type` × `location` で集計して `iot_gold` を作って。
# MAGIC > 集計項目: ユニークデバイス数、平均気温、平均湿度、読み取り件数、status='critical' 件数、status='warning' 件数」

# COMMAND ----------

# Gold 層作成: device_type × location で集計
spark.sql("""
CREATE OR REPLACE TABLE workspace.bootcamp_osaka.iot_gold AS
SELECT
  device_type,
  location,
  COUNT(DISTINCT device_id) AS device_count,
  ROUND(AVG(temperature), 1) AS avg_temperature,
  ROUND(AVG(humidity), 1) AS avg_humidity,
  COUNT(*) AS reading_count,
  SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END) AS critical_count,
  SUM(CASE WHEN status = 'warning'  THEN 1 ELSE 0 END) AS warning_count
FROM workspace.bootcamp_osaka.iot_silver
GROUP BY device_type, location
ORDER BY critical_count DESC, warning_count DESC
""")

display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_gold"))

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - `device_type` × `location` ごとに集計されている
# MAGIC - `critical_count`, `warning_count` で異常が多い組み合わせがすぐわかる
# MAGIC - 行数が少なくなり、ダッシュボードや Genie で扱いやすい形に
# MAGIC
# MAGIC → これが **Gold 層**（ビジネスで使える形に集計）

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-6. メトリックビューを作る（業務指標の定義書）
# MAGIC
# MAGIC Gold テーブルに対して **メトリックビュー** を定義します。
# MAGIC メトリックビューは「**この指標はこう計算する**」を YAML で1箇所に定義しておくしくみです。
# MAGIC
# MAGIC ### 何が嬉しいか
# MAGIC
# MAGIC - **ダッシュボード / Genie / SQL** どこから聞いても**同じ計算式**で答えが返る
# MAGIC - Genie が `critical_count` のような業務指標を**正しく理解して**回答してくれる（精度UP）
# MAGIC - 後で計算式を直したいときも、**この1箇所を直すだけ**で全員に伝わる
# MAGIC
# MAGIC ### このハンズオンで作る指標
# MAGIC
# MAGIC それぞれの dimension / measure に **日本語の説明（description）** を付けることで、Genie が日本語の質問でも指標を正しく理解できるようになります。
# MAGIC
# MAGIC | 種類 | 名前 | 説明（description） | 定義 |
# MAGIC |---|---|---|---|
# MAGIC | dimension（切り口） | `device_type` | デバイスの種類 | そのまま |
# MAGIC | dimension（切り口） | `location` | 設置場所 | そのまま |
# MAGIC | measure（指標） | `total_readings` | 読み取り件数 | `COUNT(1)` |
# MAGIC | measure（指標） | `critical_count` | 重大エラー件数 | `SUM(CASE WHEN status='critical' THEN 1 ELSE 0 END)` |
# MAGIC | measure（指標） | `avg_temperature` | 平均気温 | `AVG(temperature)` |

# COMMAND ----------

# DBTITLE 1,Cell 27
# メトリックビュー作成（iot_silver をソースに、業務指標を定義）
spark.sql("""
CREATE OR REPLACE VIEW workspace.bootcamp_osaka.iot_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: workspace.bootcamp_osaka.iot_silver
dimensions:
  - name: device_type
    expr: device_type
  - name: location
    expr: location
measures:
  - name: total_readings
    expr: COUNT(1)
  - name: critical_count
    expr: SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END)
  - name: avg_temperature
    expr: AVG(temperature)
$$
""")

print("メトリックビュー作成完了: workspace.bootcamp_osaka.iot_metrics")

# COMMAND ----------

# DBTITLE 1,Unity Catalogタグでメタデータを追加（例）
# Unity Catalogのタグ機能で個別のカラムにメタデータを付与できます
# （参考用 - 実行は任意）

# まずタグを作成
spark.sql("""
CREATE TAG IF NOT EXISTS workspace.bootcamp_osaka.metric_description
""")

# ソーステーブル（iot_silver）のカラムにタグを設定
spark.sql("""
ALTER TABLE workspace.bootcamp_osaka.iot_silver
ALTER COLUMN status SET TAG metric_description = 'デバイスのステータス（critical/warning/normal）'
""")

spark.sql("""
ALTER TABLE workspace.bootcamp_osaka.iot_silver
ALTER COLUMN temperature SET TAG metric_description = '温度（摄氏）'
""")

print("タグを追加しました")

# COMMAND ----------

# MAGIC %md
# MAGIC **確認ポイント**
# MAGIC - メトリックビューが作成された
# MAGIC - 後の Step 3 で、これを **Genie スペースに追加**して効果を体験します
# MAGIC
# MAGIC ## ✅ Step 1 完了
# MAGIC
# MAGIC ここまでで **Bronze → Silver → Gold + メトリックビュー** を手作業で通せました。
# MAGIC 次の Step 2 では、これと同じ加工を **Lakeflow Job として自動化**します。

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # 🍵 ここで 15分休憩
# MAGIC
# MAGIC ---

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 2: Lakeflow Jobs で自動化（12分）
# MAGIC
# MAGIC ここからは、UIで操作を行うため、ノートブックを離れてスライドを参照します。
# MAGIC スライドの「Step2：Lakeflow Jobs で自動化」を参照してください。
# MAGIC
# MAGIC **⏎ ノートブック上部のタブで `00_main` に戻って、Step 3 へ進みます**

# COMMAND ----------

# MAGIC %md
# MAGIC # Step 3: Genie で結果を確認（5分）
# MAGIC
# MAGIC Job の実行が成功したら、Step 1-6 で作ったメトリックビューを Genie に使わせて、業務指標が定義通りに返ってくるかを確認します。
# MAGIC
# MAGIC ## Genie でメトリックビューに質問
# MAGIC
# MAGIC 前半で体験した Genie に、**Step 1-6 で作ったメトリックビュー** を使わせてみます。
# MAGIC メトリックビューは内部で `iot_silver` を参照しているので、Genie は定義された指標で正確に回答します。
# MAGIC
# MAGIC 1. 左メニューから **「Genie」** をクリック
# MAGIC 2. 右上 **「新規」** → Genie スペース作成
# MAGIC 3. カタログ: `workspace`、スキーマ: `bootcamp_osaka`
# MAGIC 4. **`iot_metrics`** （メトリックビュー）を選択して作成
# MAGIC 5. （日本語で回答させたい場合は 設定 → 指示 に「日本語で回答して」を追加）
# MAGIC
# MAGIC 試しに以下の3問を順番に投げてみてください。それぞれメトリックビューの違う側面を体験できます：
# MAGIC
# MAGIC #### ① 業務名で1指標を聞く（**一貫性**）
# MAGIC > 「**重大エラーが一番多いのは、どのデバイス種別と設置場所の組み合わせ？**」
# MAGIC
# MAGIC #### ② 複合指標を組み立てさせる（**複合性**）
# MAGIC > 「**デバイス種別ごとに、重大エラー率（重大エラー件数 ÷ 読み取り件数）を計算して、率が高い順に並べて**」
# MAGIC
# MAGIC #### ③ 複数指標をまとめて呼ぶ（**セマンティック層 / 再利用性**）
# MAGIC > 「**設置場所ごとに、読み取り件数・重大エラー件数・平均気温をまとめて表示して**」
# MAGIC
# MAGIC ### メトリックビューの効果
# MAGIC
# MAGIC | メリット | このハンズオンでの体感ポイント |
# MAGIC |---|---|
# MAGIC | **計算ロジックの一貫性** | `critical_count` の式（`SUM(CASE WHEN status='critical' …)`）がメトリックビューに定義されているので、誰がどこ（Genie / Dashboard / BI / SQL）から聞いても **同じ計算で同じ値**が返る → 部門間で数字が食い違わない |
# MAGIC | **指標の一元管理** | 計算式は1箇所だけ。仕様変更があれば **そこだけ直せば全員に反映**（ダッシュボード20個直して回らなくていい）|
# MAGIC | **複合指標の組み立て** | `total_readings`、`critical_count` を base measure として定義しておけば、**比率のような複合指標も整合的に組み立てられる**（②で体験）|
# MAGIC | **セマンティック層** | テーブルカラム（`status`）を生で扱わず、**業務用語（`重大エラー件数`）で会話できる**。SQL を毎回書かない |
# MAGIC
# MAGIC → これが講義 Q7「Genie の精度を上げる仕組み」の答え合わせです。
# MAGIC
# MAGIC > 💡 ちなみに、メトリックビューの定義に **日本語の `description` を入れた**ことで、Genie が `重大エラー` → `critical_count` の対応も認識します。
# MAGIC > 必須ではないですが、現場で使うなら入れておくと利便性が上がります。
# MAGIC
# MAGIC **🎉 前半で体験した Genie の世界が、自分で作ったデータ + 自分で定義した指標で再現できました！**
# MAGIC
# MAGIC > 💡 補足: `iot_gold` テーブルを Genie に追加しなかったのは、**メトリックビューだけで同じ質問に答えられる**から。
# MAGIC > 1 つにまとめた方が Genie の回答も安定します。`iot_gold` は次の Step 4（SQL エディター）で使います。

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
# MAGIC ## 4-2. カタログとスキーマを選択する
# MAGIC
# MAGIC SQLエディターはノートブックと違い、**実行時にどのカタログ・スキーマを使うか自分で指定**します。
# MAGIC
# MAGIC 1. SQLエディター画面の上部にある **カタログ選択ドロップダウン** をクリック → **`workspace`** を選択
# MAGIC 2. 隣の **スキーマ選択ドロップダウン** をクリック → **`bootcamp_osaka`** を選択
# MAGIC
# MAGIC > 💡 ここで選択しておくと、以降のクエリで `workspace.bootcamp_osaka.` を省略して `iot_gold` だけで参照できます。
# MAGIC > 下のクエリ例は念のためフルパス（`workspace.bootcamp_osaka.iot_gold`）で書いてあるので、選択しなくても動きます。
# MAGIC
# MAGIC ## 4-3. SQLで分析してみる
# MAGIC
# MAGIC 以下のクエリをコピペして実行してください（`Shift + Enter`）。
# MAGIC
# MAGIC ### 例1: Gold テーブルの中身を見る
# MAGIC ```sql
# MAGIC SELECT * FROM workspace.bootcamp_osaka.iot_gold;
# MAGIC ```
# MAGIC
# MAGIC ### 例2: デバイスタイプ別の合計読み取り件数
# MAGIC ```sql
# MAGIC SELECT
# MAGIC   device_type,
# MAGIC   SUM(reading_count) AS total_readings,
# MAGIC   SUM(critical_count) AS total_critical
# MAGIC FROM workspace.bootcamp_osaka.iot_gold
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
# MAGIC FROM workspace.bootcamp_osaka.iot_gold
# MAGIC ORDER BY critical_count DESC
# MAGIC LIMIT 3;
# MAGIC ```
# MAGIC
# MAGIC ## 4-4. Genie Code を SQLエディターで使う（任意）
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