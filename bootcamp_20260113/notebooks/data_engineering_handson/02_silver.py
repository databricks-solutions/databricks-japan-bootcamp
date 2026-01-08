# Databricks notebook source
# MAGIC %md
# MAGIC # Silverテーブルの作成
# MAGIC
# MAGIC ## 概要
# MAGIC このノートブックでは、BronzeテーブルのデータをクレンジングしてSilverテーブルを作成し、Delta Lakeの機能を体験します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. パラメータ設定

# COMMAND ----------

# DBTITLE 1,ウィジェットの作成
dbutils.widgets.text("catalog_name", "workspace", "カタログ名")
dbutils.widgets.text("schema_name", "data_engineering", "スキーマ名")

# COMMAND ----------

# DBTITLE 1,ウィジェットの値を取得
catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")

print(f"📊 カタログ名: {catalog_name}")
print(f"📊 スキーマ名: {schema_name}")

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

# Bronzeテーブルの存在確認
bronze_table = f"{catalog_name}.{schema_name}.de_iot_bronze"
try:
    bronze_count = spark.sql(f"SELECT COUNT(*) FROM {bronze_table}").collect()[0][0]
    print(f"✅ Bronzeテーブル '{bronze_table}' を確認しました (レコード数: {bronze_count})")
except Exception as e:
    raise ValueError(f"❌ Bronzeテーブル '{bronze_table}' が存在しません。先にBronzeテーブルを作成してください。")

print(f"🎯 必須パラメーターのチェック完了: {catalog_name}.{schema_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Silverテーブルの作成
# MAGIC
# MAGIC ### 変換内容
# MAGIC - **クレンジング**: 空文字列・空白・N/A → NULL
# MAGIC - **型変換**: timestamp → TIMESTAMP型、temperature/humidity → DOUBLE型
# MAGIC
# MAGIC > 💡 **注意**: このハンズオンでは事前にCREATE OR **REPLACE** TABLEを実行していますが、  
# MAGIC > 実際の本番環境では既存テーブルの置き換えには注意が必要です。

# COMMAND ----------

# DBTITLE 1,Silverテーブルの作成
# テーブル名の設定
silver_table = f"{catalog_name}.{schema_name}.de_iot_silver"

print(f"📝 Silverテーブル '{silver_table}' を作成中...")

# CREATE OR REPLACE TABLE AS SELECT (CTAS) でクレンジングと型変換を実行
spark.sql(f"""
CREATE OR REPLACE TABLE {silver_table} AS
SELECT 
  device_id,
  CAST(timestamp AS TIMESTAMP) as timestamp,
  CAST(
    CASE 
      WHEN TRIM(temperature) IN ('', 'N/A') THEN NULL 
      ELSE TRIM(temperature) 
    END AS DOUBLE
  ) as temperature,
  CAST(
    CASE 
      WHEN TRIM(humidity) IN ('', 'N/A') THEN NULL 
      ELSE TRIM(humidity) 
    END AS DOUBLE
  ) as humidity,
  CASE 
    WHEN TRIM(status) = '' THEN NULL 
    ELSE TRIM(status) 
  END as status,
  ingestion_time,
  current_timestamp() as processed_time
FROM {bronze_table}
""")

print("✅ Silverテーブルの作成が完了しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. データ内容の確認

# COMMAND ----------

# DBTITLE 1,データ内容の確認
print("=== Silverテーブルのデータ内容（クレンジング済み）===")
silver_df = spark.sql(f"SELECT * FROM {silver_table}")
silver_df.show(truncate=False)

print(f"📊 総レコード数: {silver_df.count()}")
print("✅ データクレンジングが正常に完了しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. データ更新とバージョン管理

# COMMAND ----------

# DBTITLE 1,データ更新の実行
# 更新前のバージョンを記録
current_version = spark.sql(f"SELECT MAX(version) FROM (DESCRIBE HISTORY {silver_table})").collect()[0][0]
print(f"📝 更新前のバージョン: {current_version}")

# 特定のデバイスのステータスを更新
print("🔄 データを更新中...")
spark.sql(f"""
UPDATE {silver_table} 
SET status = 'updated', processed_time = current_timestamp()
WHERE device_id = 'DEV001'
""")

print("✅ DEV001のステータスを'updated'に更新しました")

# 更新後のバージョンを確認
new_version = spark.sql(f"SELECT MAX(version) FROM (DESCRIBE HISTORY {silver_table})").collect()[0][0]
print(f"🔄 バージョンが {current_version} → {new_version} に更新されました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Time Travel体験

# COMMAND ----------

# DBTITLE 1,Time Travelでのデータ確認
print(f"⏰ Time Travel: バージョン{current_version}（更新前）のデータを確認")
time_travel_df = spark.sql(f"""
SELECT * FROM {silver_table} VERSION AS OF {current_version}
WHERE device_id = 'DEV001'
""")
time_travel_df.show(truncate=False)

print(f"⏰ 現在のバージョン{new_version}（更新後）のデータを確認")
current_df = spark.sql(f"""
SELECT * FROM {silver_table}
WHERE device_id = 'DEV001'
""")
current_df.show(truncate=False)

print("🎉 Time Travelにより、過去のバージョンのデータを参照できました！")

# COMMAND ----------

# DBTITLE 1,テーブル名を返却
dbutils.notebook.exit(silver_table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. まとめ
# MAGIC
# MAGIC ✅ **Silverテーブルの作成が完了しました！**
# MAGIC
# MAGIC ### 実行内容
# MAGIC - BronzeテーブルからSilverテーブルへの変換
# MAGIC - データクレンジング（空文字列・N/A → NULL）
# MAGIC - 型変換（STRING → TIMESTAMP, DOUBLE）
# MAGIC - UPDATE操作とバージョン管理
# MAGIC - Time Travelによる過去データ参照
# MAGIC
# MAGIC ### Delta Lake機能
# MAGIC - **ACID特性**: 信頼性の高いデータ更新
# MAGIC - **バージョン管理**: すべての変更が記録
# MAGIC - **Time Travel**: 過去の任意の時点のデータ参照
# MAGIC
# MAGIC ### 次のステップ
# MAGIC メインノートブックに戻って、ワークフローの作成に進んでください。
