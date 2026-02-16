# Databricks notebook source
# MAGIC %md
# MAGIC # Databricks データエンジニアリング ハンズオン
# MAGIC このハンズオンでは、Databricksを使用したデータエンジニアリングの基本的な流れを学習します。実行するステップは以下の通りです。
# MAGIC 
# MAGIC 1. ウィジェットを使用したパラメーター設定
# MAGIC 2. データファイルをUnity Catalogボリュームにアップロード
# MAGIC 3. Bronzeテーブルの作成
# MAGIC 4. Silverテーブルの作成
# MAGIC 5. Databricksワークフローの作成と実行
# MAGIC
# MAGIC 本ノートブックを実行することで、上記の1〜4までの処理が自動的に実行されます。受講者は実行結果を確認し、各ステップで何が行われたかを理解できます。
# MAGIC
# MAGIC 5のワークフローの作成は、**受講者が手動で行う**必要があります。作成手順自体を本ノートブックに記載していますので、受講者はその手順に従ってワークフローを作成します。
# MAGIC 
# MAGIC ## 所要時間
# MAGIC 約35分

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: ウィジェットを使用したパラメーター設定
# MAGIC 1. 以下の**「ウィジェットの作成」セルを実行**してウィジェットを作成します
# MAGIC 2. **ウィジェットに値を入力**します
# MAGIC    - **カタログ名**: `dbacademy`（固定）
# MAGIC    - **スキーマ名**: `labuser`から始まるスキーマ名を指定
# MAGIC 3. ノートブック右上にある**「すべてを実行」**をクリックします
# MAGIC 4. 各セルの実行結果を順次確認しながら、すべてのセルが**成功することを確認**します
# MAGIC    - すべてのセルの処理に**約3-4分**かかります

# COMMAND ----------

# DBTITLE 1,ウィジェットの作成
dbutils.widgets.text("catalog_name", "dbacademy", "カタログ名")
dbutils.widgets.text("schema_name", "", "スキーマ名")

# COMMAND ----------

# DBTITLE 1,ウィジェットの値を取得
catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")

print(f"📊 カタログ名: {catalog_name}")
print(f"📊 スキーマ名: {schema_name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ### Note: ウィジェットの値チェックについて
# MAGIC - 以下の「必須パラメータのチェック」セルで、ウィジェットの値が正しく設定されているかが自動的にチェックされます
# MAGIC - もし指定した値に不備がある場合、エラーメッセージが表示されますので、指示に従って修正してください
# MAGIC     - 特に、スキーマのところに `dbacademy.` というカタログ名までコピーしてしまわないよう注意してください
# MAGIC - 必須パラメータのチェック以外のセルでは基本的にエラーは起きない想定です。もしエラーが起きた場合、講師にお声がけください

# COMMAND ----------

# DBTITLE 1,必須パラメータのチェック
# ウィジェットに値が設定されているか確認
if not catalog_name:
    raise ValueError("❌ カタログ名が指定されていません。ウィジェットでカタログ名を設定してください。")
if not schema_name:
    raise ValueError("❌ スキーマ名が指定されていません。ウィジェットでスキーマ名を設定してください。")

print(f"カタログ名: {catalog_name}")
print(f"スキーマ名: {schema_name}")

# カタログの存在確認
try:
    spark.sql(f"USE CATALOG {catalog_name}")
    print(f"✅ カタログ '{catalog_name}' の確認が完了しました")
except Exception as e:
    raise ValueError(f"❌ カタログ '{catalog_name}' が存在しません。正しいカタログ名を指定してください。")

# スキーマの存在確認
try:
    spark.sql(f"USE SCHEMA {schema_name}")
    print(f"✅ スキーマ '{schema_name}' の確認が完了しました")
except Exception as e:
    raise ValueError(f"❌ スキーマ '{schema_name}' が存在しません。正しいスキーマ名を指定してください。")

print(f"🎯 必須パラメーターのチェック完了: {catalog_name}.{schema_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: データファイルをUnity Catalogボリュームにアップロード
# MAGIC ノートブックで「すべてを実行」をクリックすることで、本ステップは自動的に実行されます。本ステップで実行される処理は以下の通りです。
# MAGIC
# MAGIC 1. **Unity Catalogボリュームの作成**
# MAGIC 2. **データファイルのボリュームへのアップロード**

# COMMAND ----------

# DBTITLE 1,ボリュームの作成
# ボリュームのパスを定義
volume_path = f"{catalog_name}.{schema_name}.files"

try:
   # ボリュームが既に存在するかチェック
   spark.sql(f"DESCRIBE VOLUME {volume_path}")
   print(f"ℹ️ ボリューム '{volume_path}' は既に存在します")
except:
   # ボリュームが存在しない場合は作成
   spark.sql(f"CREATE VOLUME IF NOT EXISTS {volume_path}")
   print(f"✅ ボリューム '{volume_path}' を作成しました")

# COMMAND ----------

# DBTITLE 1,データファイルをボリュームに作成
# データファイルのパスを定義
destination_path = f"/Volumes/{catalog_name}/{schema_name}/files/de_iot_data.csv"

# データファイル用のサンプルデータを定義
sample_data = """device_id,timestamp,temperature,humidity,status
DEV001,2024-01-01 10:00:00,23.5,65.2,active
DEV002,2024-01-01 10:01:00,"",70.1,inactive
DEV003,2024-01-01 10:02:00,25.8," ",active
DEV004,2024-01-01 10:03:00,N/A,68.9,error
DEV005,2024-01-01 10:04:00,24.7,N/A,active
DEV006,2024-01-01 10:05:00,26.3,71.2,
DEV007,2024-01-01 10:06:00,22.8,63.5,active
DEV008,2024-01-01 10:07:00,25.1,67.9,maintenance
DEV009,2024-01-01 10:08:00,"",64.8,active
DEV010,2024-01-01 10:09:00,24.3,N/A,inactive"""

# dbutilsを使用してボリュームにファイルを直接作成
dbutils.fs.put(destination_path, sample_data, overwrite=True)
print(f"✅ ファイルを '{destination_path}' に作成しました")

# COMMAND ----------

# DBTITLE 1,作成されたファイルの確認
try:
   df_check = spark.read.option("header", "true").csv(destination_path)
   print("✅ ファイルの作成が完了しています")
   print(f"📁 ファイルパス: {destination_path}")
   print(f"📊 レコード数: {df_check.count()}")
   print("\n📋 データプレビュー:")
   df_check.show(5, truncate=False)

   print("\n👀 GUIでボリュームにあるファイルを確認してみてください")
   print(f"左サイドバー > Catalog > {catalog_name} > {schema_name} > ボリューム > files > de_iot_data.csv")
   
except Exception as e:
   print(f"❌ ファイルの作成に失敗しました: {e}")
   raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Bronzeテーブル作成
# MAGIC ノートブックで「すべてを実行」をクリックすることで、本ステップは自動的に実行されます。本ステップで実行される処理は以下の通りです。

# MAGIC 1. `01_bronze_layer`ノートブックを実行し、Bronzeテーブルを作成

# COMMAND ----------

# DBTITLE 1,Bronzeテーブル作成用ノートブックの実行
print("🚀 Bronzeテーブル作成用ノートブックを実行中...")
bronze_table_name = dbutils.notebook.run("./01_bronze", 300, {
    "catalog_name": catalog_name,
    "schema_name": schema_name
})

print("✅ Bronzeテーブルの作成が完了しました")
print(f"👀 テーブル名: {bronze_table_name} - カタログエクスプローラーで内容を確認してください")
print("👀 ノートブックのワークフローの開始時刻のリンクをクリックし、実行された内容を確認してください")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Silverテーブル作成
# MAGIC ノートブックで「すべてを実行」をクリックすることで、本ステップは自動的に実行されます。本ステップで実行される処理は以下の通りです。

# MAGIC 1. `02_silver_layer`ノートブックを実行し、Silverテーブルを作成

# COMMAND ----------

# DBTITLE 1,Silverテーブル作成用ノートブックの実行
print("🚀 Silverテーブル作成用ノートブックを実行中...")
silver_table_name = dbutils.notebook.run("./02_silver", 300, {
    "catalog_name": catalog_name,
    "schema_name": schema_name
})

print("✅ Silverテーブルの作成が完了しました")
print(f"👀 テーブル名: {silver_table_name} - カタログエクスプローラーで内容を確認してください")
print("👀 ノートブックのワークフローの開始時刻のリンクをクリックし、実行された内容を確認してください")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: ジョブの作成
# MAGIC ここから、受講者が手動でジョブを作成します。以下の手順で作業を進めてください。
# MAGIC 
# MAGIC > 💡 **Note**: ジョブの作成はAPI/CLI/SDKを使った自動化が可能ですが、学習のために手動で作成します。
# MAGIC
# MAGIC ### 1. ジョブの作成
# MAGIC 1. 左サイドバーの**「ワークフロー」**をクリック
# MAGIC 2. 「ジョブとパイプライン」の画面で右上の**「作成」**ボタンをクリック > **「ジョブ」**を選択
# MAGIC
# MAGIC     ![create-job](../../images/data_engineering_handson/create-job.png)
# MAGIC 3. ジョブ名に `de_iot_job` と入力
# MAGIC
# MAGIC ### 2. タスク1の作成（Bronzeテーブル作成用ノートブック）
# MAGIC 1. 名前のないタスクが表示されるので、以下の項目を設定
# MAGIC     - **タスク名**: `01_bronze`
# MAGIC     - **タイプ**: `ノートブック`
# MAGIC     - **ソース**: `ワークスペース`
# MAGIC     - **パス**: ノートブックを選択をクリックし、以下のパスを選択
# MAGIC         - `{home_dir}/komae_dbdemos/bootcamp_20250527/notebooks/data_engineering_handson/01_bronze`
# MAGIC     - **クラスター**: `サーバーレス` (デフォルトから変更しない)
# MAGIC 2. **「タスクを作成」**をクリック
# MAGIC
# MAGIC    ![create-task-bronze](../../images/data_engineering_handson/create-task-bronze.png)
# MAGIC 
# MAGIC ### 3. タスク2の作成（Silverテーブル作成用ノートブック）
# MAGIC 1. **「タスクを追加」** をクリック > **「ノートブック」**を選択
# MAGIC 2. 名前のないタスクが表示されるので、以下の項目を設定
# MAGIC     - **タスク名**: `02_silver`
# MAGIC     - **タイプ**: `ノートブック`
# MAGIC     - **ソース**: `ワークスペース`
# MAGIC     - **パス**: ノートブックを選択をクリックし、以下のパスを選択
# MAGIC         - `{home_dir}/komae_dbdemos/bootcamp_20250527/notebooks/data_engineering_handson/02_silver`
# MAGIC     - **依存先**: `01_bronze` (デフォルトで選択されているはず)
# MAGIC     - **依存関係がある場合に実行**: `すべて成功しました` (デフォルトで選択されているはず)
# MAGIC 3. **「タスクを作成」**をクリック
# MAGIC
# MAGIC    ![create-task-silver](../../images/data_engineering_handson/create-task-silver.png)
# MAGIC
# MAGIC ### 4. ジョブパラメーターの定義
# MAGIC 1. ジョブの画面右側の **「パラメーターを編集」**をクリック
# MAGIC 2. **「パラメーター」**セクションで以下の項目を設定
# MAGIC     - **キー**: `catalog_name`, **値**: `dbacademy`
# MAGIC     - **キー**: `schema_name`, **値**: `labuser` から始まるスキーマ名
# MAGIC 3. **「保存」**をクリック
# MAGIC
# MAGIC     ![define-job-parameters](../../images/data_engineering_handson/define-job-parameters.png)
# MAGIC
# MAGIC ### 5. スケジュールの設定
# MAGIC > 💡 **Note**: この後すぐにマニュアルで実行するのでスケジュール設定に意味は無いのですが、学習のために実施します。
# MAGIC
# MAGIC 1. ジョブの画面右側の **「トリガーを追加」**をクリック
# MAGIC 2. **「トリガータイプ」**を `スケジュール済み` に設定し、以下の項目を設定
# MAGIC     - **スケジュールのタイプ**: `Simple`
# MAGIC     - **定期的**: Every `1` `時間`
# MAGIC 3. **「保存」**をクリック
# MAGIC
# MAGIC     ![define-trigger](../../images/data_engineering_handson/define-job-trigger.png)
# MAGIC
# MAGIC ### 6. ジョブの実行
# MAGIC 1. ジョブの画面右上の **「今すぐ実行」** ボタンをクリック
# MAGIC 2. **「ジョブの実行」**タブに切り替えて実行状況を確認、ステータスが `成功` になることを確認
# MAGIC 3. ジョブの開始時刻のリンクをクリックして、実行された内容を確認
# MAGIC
# MAGIC     ![run-job](../../images/data_engineering_handson/run-job.png)

# COMMAND ----------

# MAGIC %md
# MAGIC 以上でデータエンジニアリング ハンズオンは終了です。お疲れ様でした。