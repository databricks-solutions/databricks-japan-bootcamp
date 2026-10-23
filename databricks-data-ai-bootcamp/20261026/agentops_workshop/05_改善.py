# Databricks notebook source
# MAGIC %md
# MAGIC # 05. 改善: 改善版を同じ評価データで評価し、初版と比べる（約10分）
# MAGIC
# MAGIC | # | やること | 使う機能 |
# MAGIC |---|---|---|
# MAGIC | 1 | 改善版（v2）で何を変えたかを見る | ― |
# MAGIC | 2 | 同じ評価データで v2 を評価し、v1 と比べる | 評価の比較（品質・レイテンシ・トークン数） |
# MAGIC
# MAGIC `04_評価` を実行したあとに進めます（04 で登録した評価データと、初版の評価結果を使います）。

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]==3.17.1" "databricks-langchain==0.21.0" "databricks-mcp==0.9.2" "langgraph>=1.1" "langchain>=1.0" "databricks-sdk>=0.124.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

import os
import sys

import mlflow
import mlflow.genai.datasets as ds
import pandas as pd

os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "4"   # 同時に呼びすぎない（ツールの呼び出しが断られるのを防ぐ）
experiment = use_experiment()
sys.path.insert(0, APP_DIR)
import agent_v2
from evaluation import SCORE_COLUMNS, add_japanese_reasons, assessments_table, make_predict_fn, make_scorers
from tools import to_text

dataset = ds.get_dataset(name=EVAL_DATASET)   # 04 で登録した評価データ
scorers = make_scorers(JUDGE_ENDPOINT)        # 04 と同じ採点器
run_v1 = mlflow.search_runs(filter_string="tags.agent_version = 'v1' and attributes.run_name LIKE 'eval_%'",
                            order_by=["start_time DESC"], max_results=1, output_format="list")[0]   # 04 の初版の評価
print("初版の評価:", run_v1.info.run_name, run_v1.info.run_id)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 改善版（v2）で何を変えたかを見る
# MAGIC 改善は2か所です（`app/agent_v2.py`）。
# MAGIC 1. **システムプロンプト**: 手順（製品情報の照会を最初に行う、無償点検の対象かを確かめる）・守るルール・回答の形式を加える
# MAGIC 2. **検索のツール**: 照会した型番（と全製品共通の `ALL`）で絞り込んで検索する

# COMMAND ----------

import difflib
from pathlib import Path

v1, v2 = (Path(APP_DIR, f).read_text().splitlines() for f in ["agent_v1.py", "agent_v2.py"])
print("\n".join(difflib.unified_diff(v1, v2, "agent_v1.py", "agent_v2.py", lineterm="", n=0)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 同じ評価データで v2 を評価し、v1 と比べる

# COMMAND ----------

with mlflow.start_run(run_name="eval_v2_改善版") as run_v2:
    mlflow.set_tag("agent_version", "v2")
    results_v2 = mlflow.genai.evaluate(data=dataset, predict_fn=make_predict_fn(agent_v2.build_agent(), to_text), scorers=scorers)

# COMMAND ----------


def trace_stats(run_id: str) -> dict:
    """評価の run のトレースから、1件あたりの時間（秒）とトークン数の平均を出す。"""
    traces = mlflow.search_traces(run_id=run_id, return_type="list")
    seconds = [t.info.execution_duration / 1000 for t in traces if t.info.execution_duration]
    tokens = [(t.info.token_usage or {}).get("total_tokens", 0) for t in traces]
    return {"1件あたりの時間（秒）": round(sum(seconds) / len(seconds), 1) if seconds else None,
            "1件あたりのトークン数": round(sum(tokens) / len(tokens)) if tokens else None}


compare = pd.DataFrame({
    "v1（初版）": {**{k: round(v, 2) for k, v in run_v1.data.metrics.items() if k.endswith("/mean")}, **trace_stats(run_v1.info.run_id)},
    "v2（改善版）": {**{k: round(v, 2) for k, v in results_v2.metrics.items() if k.endswith("/mean")}, **trace_stats(run_v2.info.run_id)},
})
compare

# COMMAND ----------

# MAGIC %md
# MAGIC 確かめること:
# MAGIC - 上がった指標と、**下がった指標がないか**（下がっていたら、そのケースのトレースと理由を見る）
# MAGIC - LLM ジャッジの採点は、実行ごとに多少ぶれます。差が小さい指標は、ケースごとの結果も見て判断します
# MAGIC - 品質と引き換えに、時間やトークン数がどれだけ増えたか
# MAGIC
# MAGIC MLflow の画面（Experiments → `agentops_traces` → Evaluations）で2つの評価を選ぶと、ケースごとに並べて比べられます。

# COMMAND ----------

table_v2 = add_japanese_reasons(assessments_table(run_v2.info.run_id), _w, LLM_ENDPOINT)
display(table_v2[["question"] + [c for name in SCORE_COLUMNS for c in (name, f"{name}_理由") if c in table_v2]])

# COMMAND ----------

# MAGIC %md
# MAGIC → 品質を確かめた v2 を、`06_デプロイと監視` でアプリとしてデプロイします。
