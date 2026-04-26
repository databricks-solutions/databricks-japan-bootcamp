# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze層構築 — IoT センサーデータに取込メタデータを付与
# MAGIC
# MAGIC このノートブックは **Lakeflow Job のタスクとしても、手動実行としても動く**ように作られています。
# MAGIC UI でアップロード済みの `iot_data` テーブルに **取込時刻 `ingestion_time`** を付与して `iot_bronze` を作成します。
# MAGIC
# MAGIC ## 入出力
# MAGIC - **入力**: `workspace.bootcamp_osaka.iot_data`（UI で CSV アップロードして作成済み）
# MAGIC - **出力**: `workspace.bootcamp_osaka.iot_bronze`
# MAGIC
# MAGIC ## 処理内容
# MAGIC - 元データ（`iot_data`）の全カラムをそのまま保持
# MAGIC - 取込時刻 `ingestion_time` を付与
# MAGIC
# MAGIC ## ⚠️ 事前条件
# MAGIC - 接続先: **「サーバーレス」**（ノートブック用コンピュート）
# MAGIC - スキーマ `workspace.bootcamp_osaka` 作成済み
# MAGIC - テーブル `workspace.bootcamp_osaka.iot_data`（UI アップロード済み）

# COMMAND ----------

# Bronze 層作成（iot_data + ingestion_time）
spark.sql("""
CREATE OR REPLACE TABLE workspace.bootcamp_osaka.iot_bronze AS
SELECT
  *,
  current_timestamp() AS ingestion_time
FROM workspace.bootcamp_osaka.iot_data
""")

# COMMAND ----------

# 結果確認
result = spark.sql("SELECT COUNT(*) AS row_count FROM workspace.bootcamp_osaka.iot_bronze")
display(result)
display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_bronze LIMIT 5"))
