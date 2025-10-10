# Databricks notebook source
# MAGIC %md
# MAGIC # Bronzeテーブルの作成
# MAGIC
# MAGIC ## 概要
# MAGIC このノートブックでは、生データ（CSV）をDelta Lake形式のBronzeテーブルとして取り込みます。

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

print(f"🎯 必須パラメーターのチェック完了: {catalog_name}.{schema_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Bronzeテーブルの作成
# MAGIC > 💡 **注意**: このハンズオンでは事前にCREATE OR **REPLACE** TABLEを実行していますが、  
# MAGIC > 実際の本番環境では既存テーブルの置き換えには注意が必要です。

# COMMAND ----------

# DBTITLE 1,Bronzeテーブルの作成
# CSVファイルのパスとテーブル名を設定
csv_file_path = f"/Volumes/{catalog_name}/{schema_name}/files/de_iot_data.csv"
table_name = f"{catalog_name}.{schema_name}.de_iot_bronze"

print(f"📝 Bronzeテーブル '{table_name}' を作成中...")

# CREATE OR REPLACE TABLEでテーブル構造を定義
spark.sql(f"""
CREATE OR REPLACE TABLE {table_name} (
  device_id STRING,
  timestamp STRING,
  temperature STRING,
  humidity STRING,
  status STRING,
  ingestion_time TIMESTAMP
) USING DELTA
""")

print("✅ Bronzeテーブルの作成が完了しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. データ取り込み（COPY INTO）

# COMMAND ----------

# DBTITLE 1,COPY INTOコマンドでデータを取り込み
print(f"🚀 データを '{table_name}' に取り込み中...")

result = spark.sql(f"""
COPY INTO {table_name}
FROM (
  SELECT 
    device_id,
    timestamp,
    temperature,
    humidity,
    status,
    current_timestamp() as ingestion_time
  FROM '{csv_file_path}'
)
FILEFORMAT = CSV
FORMAT_OPTIONS ('mergeSchema' = 'true', 'header' = 'true')
COPY_OPTIONS ('mergeSchema' = 'true')
""")

result.show()
print("✅ データ取り込みが完了しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. データ内容の確認

# COMMAND ----------

# DBTITLE 1,データ内容の確認
print("=== Bronzeテーブルのデータ内容 ===")
bronze_df = spark.sql(f"SELECT * FROM {table_name}")
bronze_df.show(truncate=False)

print(f"📊 総レコード数: {bronze_df.count()}")
print("💡 Bronzeテーブルでは生データをそのまま保存しています")

# COMMAND ----------

# DBTITLE 1,テーブル名を返却
dbutils.notebook.exit(table_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. まとめ
# MAGIC
# MAGIC ✅ **Bronzeテーブルの作成が完了しました！**
# MAGIC
# MAGIC ### 実行内容
# MAGIC - CSVファイルからDelta Lakeテーブルを作成
# MAGIC - COPY INTOによる冪等な取り込み処理
# MAGIC - 全カラムをSTRING型で生データを忠実に保存
# MAGIC
# MAGIC ### 次のステップ
# MAGIC メインノートブックに戻って、Silverテーブルの作成に進んでください。
