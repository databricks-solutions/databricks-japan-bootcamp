# Databricks notebook source
# MAGIC %md
# MAGIC # Gold層構築 — ビジネス指標への集計
# MAGIC
# MAGIC このノートブックは **Lakeflow Job のタスクとしても、手動実行としても動く**ように作られています。
# MAGIC `iot_silver` を `device_type` × `location` で集計し、ビジネス目線の `iot_gold` テーブルを作成します。
# MAGIC
# MAGIC ## 入出力
# MAGIC - **入力**: `workspace.bootcamp_osaka.iot_silver`
# MAGIC - **出力**: `workspace.bootcamp_osaka.iot_gold`
# MAGIC
# MAGIC ## 集計内容
# MAGIC - `device_count`: ユニークなデバイス数
# MAGIC - `avg_temperature`, `avg_humidity`: 平均気温・湿度
# MAGIC - `reading_count`: 読み取り件数
# MAGIC - `critical_count`, `warning_count`: ステータス別件数
# MAGIC
# MAGIC ## ⚠️ 事前設定
# MAGIC - 接続先: **「サーバーレス」**
# MAGIC - `iot_silver` テーブルが存在すること（先に 02_silver を実行 or Job 内で前段タスク完了済み）

# COMMAND ----------

# Silver → Gold 集計（CREATE OR REPLACE で冪等）
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

# COMMAND ----------

# 結果確認
display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_gold"))
