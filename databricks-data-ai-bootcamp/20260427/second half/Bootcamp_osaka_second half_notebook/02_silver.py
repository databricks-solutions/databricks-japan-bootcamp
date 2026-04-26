# Databricks notebook source
# MAGIC %md
# MAGIC # Silver層構築 — Bronze データのクレンジング + 型変換
# MAGIC
# MAGIC このノートブックは **Lakeflow Job のタスクとしても、手動実行としても動く**ように作られています。
# MAGIC `iot_bronze` の生データを型変換・NULL処理して `iot_silver` を作成します。
# MAGIC
# MAGIC ## 入出力
# MAGIC - **入力**: `workspace.bootcamp_osaka.iot_bronze`
# MAGIC - **出力**: `workspace.bootcamp_osaka.iot_silver`
# MAGIC
# MAGIC ## 処理内容
# MAGIC - `timestamp` を STRING → TIMESTAMP 型に変換
# MAGIC - `temperature`, `humidity` を STRING → DOUBLE 型に変換
# MAGIC - 空文字 `''` と `'N/A'` を NULL に変換
# MAGIC - 異常値（temperature = `'999'`）を除外
# MAGIC
# MAGIC ## ⚠️ 事前設定
# MAGIC - 接続先: **「サーバーレス」**
# MAGIC - `iot_bronze` テーブルが存在すること（先に 01_bronze を実行 or Job 内で前段タスク完了済み）

# COMMAND ----------

# Bronze → Silver 変換（CREATE OR REPLACE で冪等）
# Delta Lake は履歴を保持するため、CREATE OR REPLACE しても Time Travel で過去バージョンを参照可能
#
# TRY_CAST を使用: 不正値（''、'N/A'、想定外の文字列など）を NULL に自動変換
# （Spark ANSI モードでは CAST が厳格で '' → DOUBLE がエラーになるため）
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

# COMMAND ----------

# 結果確認
result = spark.sql("SELECT COUNT(*) AS row_count FROM workspace.bootcamp_osaka.iot_silver")
display(result)
display(spark.sql("SELECT * FROM workspace.bootcamp_osaka.iot_silver LIMIT 5"))
