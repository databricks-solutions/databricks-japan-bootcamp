# Databricks notebook source
# MAGIC %md
# MAGIC # 07. デプロイと監視: 品質を確かめた v2 をアプリにする（約15分）
# MAGIC
# MAGIC | # | やること | 使う機能 |
# MAGIC |---|---|---|
# MAGIC | 1 | `app/` のフォルダを、そのままアプリとしてデプロイする | Databricks Apps |
# MAGIC | 2 | チャット画面から相談を入れる | アプリのチャット画面 |
# MAGIC | 3 | アプリからのやり取りが、開発時と同じ実験にトレースとして入ることを確かめる | MLflow Tracing（Unity Catalog） |
# MAGIC
# MAGIC `app/` の中身:
# MAGIC
# MAGIC | ファイル | 内容 |
# MAGIC |---|---|
# MAGIC | `agent_v2.py`・`tools.py` | 06 で評価したエージェント（そのまま使う） |
# MAGIC | `agent/agent.py`・`runtime/` | エージェントを HTTP の API（`/api/invocations`）として公開するサーバー（AgentKit の `DurableAgentServer`） |
# MAGIC | `ui/` | チャット画面 |
# MAGIC | `app.yaml`・`requirements.txt` | 起動のしかたと、使うパッケージ |

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]==3.17.1" "databricks-sdk>=0.124.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. デプロイする
# MAGIC 04 で作り始めたアプリに、`app/` のコードをデプロイします（初回は2分ほど）。画面からは、**Compute → Apps → アプリ → Deploy** で、ソースに `app` のフォルダを指定するのと同じです。

# COMMAND ----------

from apps_helper import app_spec, deploy_app

experiment = use_experiment()
spec = app_spec(APP_NAME, experiment.experiment_id, LLM_ENDPOINT, DOC_INDEX, CASE_INDEX, PRODUCT_FUNCTION, TRACE_TABLES)
app, deployment = deploy_app(_w, spec, APP_DIR)
print(deployment.status.state, deployment.status.message)
displayHTML(f'<a href="{app.url}" target="_blank">チャット画面を開く: {app.url}</a>')

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. チャット画面から相談を入れる
# MAGIC 上のリンクからチャット画面を開き、「例を試す」のボタンを押すか、相談の文章を入れて送ります。
# MAGIC 回答の途中で、どのツールを呼んだかも表示されます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. アプリからのやり取りを、トレースで確かめる
# MAGIC チャット画面で何件か相談したあとに、次のセルを実行します。アプリからのやり取りも、04〜06 と同じ実験に入っています。
# MAGIC MLflow の画面（Experiments → `agentops_traces` → Traces）でも、1件ずつ開いて確認できます。

# COMMAND ----------

import mlflow
import pandas as pd

rows = []
for t in mlflow.search_traces(locations=[experiment.experiment_id], max_results=10, order_by=["timestamp_ms DESC"], return_type="list"):
    tools = [s.name for s in t.data.spans if s.span_type == "TOOL"]
    rows.append({"時刻": pd.to_datetime(t.info.request_time, unit="ms"), "状態": t.info.state.value,
                 "時間（秒）": round((t.info.execution_duration or 0) / 1000, 1), "呼んだツール": " → ".join(tools),
                 "相談": (t.info.request_preview or "")[:80]})
display(pd.DataFrame(rows))

# COMMAND ----------

# MAGIC %md
# MAGIC トレースは Delta テーブルなので、運用の監視（件数・時間・エラーの推移など）も SQL で集計できます。

# COMMAND ----------

display(spark.sql(f"""
  SELECT date_trunc('HOUR', timestamp_millis(CAST(start_time_unix_nano / 1000000 AS BIGINT))) AS `時刻`,
         count(DISTINCT trace_id) AS `件数`,
         round(avg((end_time_unix_nano - start_time_unix_nano) / 1e9), 1) AS `平均の時間（秒）`
  FROM {S}.{TRACE_TABLE_PREFIX}_otel_spans
  WHERE parent_span_id IS NULL OR parent_span_id = ''
  GROUP BY 1 ORDER BY 1 DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC これで、データの準備 → エージェントの開発 → 評価と改善 → デプロイ → 本番のトレースまで、Databricks の中で一通り行いました。
# MAGIC 終わったら `99_クリーンアップ` で、作ったものを削除できます。
