# Databricks notebook source
# MAGIC %md
# MAGIC # 05. 評価: デプロイの前に、初版の品質を数値で確かめる（約12分）
# MAGIC
# MAGIC | # | やること | 使う機能 |
# MAGIC |---|---|---|
# MAGIC | 1 | 評価データを Unity Catalog に登録する | 評価データセット |
# MAGIC | 2 | 初版（v1）を評価する | `mlflow.genai.evaluate`・LLM ジャッジ |
# MAGIC | 3 | 落ちたケースの理由とトレースを見る | MLflow Tracing |

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]==3.17.1" "databricks-langchain==0.21.0" "databricks-mcp==0.9.2" "langgraph>=1.1" "langchain>=1.0" "databricks-sdk>=0.124.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

import os
import sys

import mlflow
import pandas as pd

os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "4"   # 同時に呼びすぎない（ツールの呼び出しが断られるのを防ぐ）
experiment = use_experiment()
sys.path.insert(0, APP_DIR)
import agent_v1
from evaluation import SCORE_COLUMNS, add_japanese_reasons, assessments_table, eval_records, make_predict_fn, make_scorers
from tools import to_text

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 評価データを登録する
# MAGIC 過去の問い合わせから10件を選び、正解（回答に含まれるべき事実・正しい型番）を付けたものです（`data/eval_cases.json`）。
# MAGIC
# MAGIC | ケースの種類 | 件数 | 見たいこと |
# MAGIC |---|---|---|
# MAGIC | 無償点検の対象（RC-500） | 3 | 無償点検の案内が漏れないか |
# MAGIC | 似た型番（RC-550） | 3 | RC-500 の説明書と取り違えないか |
# MAGIC | 修理がいらない | 2 | 使い方の案内で解決できるものを、正しく案内できるか |
# MAGIC | 安全に関わる症状 | 2 | 使用中止を案内できるか |

# COMMAND ----------

import mlflow.genai.datasets as ds

records = eval_records()
try:
    ds.delete_dataset(name=EVAL_DATASET)
except Exception:
    pass
dataset = ds.create_dataset(name=EVAL_DATASET)
dataset.merge_records(records)
display(pd.DataFrame([{**r["inputs"], **r["expectations"], **r["tags"]} for r in records]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 初版（v1）を評価する
# MAGIC
# MAGIC | 種類 | 採点器 | 見ること |
# MAGIC |---|---|---|
# MAGIC | 組み込み | `Correctness` | 回答に正解の事実が含まれるか |
# MAGIC | 組み込み | `RetrievalGroundedness` | 回答が、検索した文書に基づいているか |
# MAGIC | 組み込み | `RelevanceToQuery` | 相談の内容に答えているか |
# MAGIC | カスタム（コード） | `retrieved_model_matches` | 検索した文書が、正しい型番のものだけか（**トレースを見て採点する**） |
# MAGIC | カスタム（LLM ジャッジ） | `safety` | 分解の案内をしない・危険な症状では使用中止を案内する |
# MAGIC
# MAGIC 2〜3分かかります。

# COMMAND ----------

scorers = make_scorers(JUDGE_ENDPOINT)
with mlflow.start_run(run_name="eval_v1_初版") as run_v1:
    mlflow.set_tag("agent_version", "v1")
    results_v1 = mlflow.genai.evaluate(data=dataset, predict_fn=make_predict_fn(agent_v1.build_agent(), to_text), scorers=scorers)
pd.Series({k: v for k, v in results_v1.metrics.items() if k.endswith("/mean")}, name="v1").to_frame()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 落ちたケースの理由とトレースを見る
# MAGIC 組み込みの採点器は理由を英語で書くので、日本語に訳して並べます。
# MAGIC MLflow の画面（Experiments → `agentops_traces` → Evaluations）でも、1件ずつ理由とトレースを確認できます。

# COMMAND ----------

table_v1 = add_japanese_reasons(assessments_table(run_v1.info.run_id), _w, LLM_ENDPOINT)
cols = ["question"] + [c for name in SCORE_COLUMNS for c in (name, f"{name}_理由") if c in table_v1]
display(table_v1[cols])

# COMMAND ----------

# MAGIC %md
# MAGIC 落ちたケースがあれば、トレースを開いて、次のことを確かめてください。
# MAGIC - どのツールが、どの順で呼ばれたか（製品情報の照会をしているか）
# MAGIC - 検索にどんな検索文を渡し、結果にどの型番の文書が入っていたか
# MAGIC
# MAGIC 回答の文面だけでは正しく見えても、トレースを見ると根拠の取り方に問題がある場合があります。

# COMMAND ----------

# MAGIC %md
# MAGIC → `06_改善` で、改善版（v2）を同じ評価データで評価し、初版と比べます。

# COMMAND ----------

# MAGIC %md
# MAGIC Genie Codeを利用して、今回の評価結果を分析しましょう。右の紫のランプマークをクリックし、Genie Codeを開いて、下記の通り指示をしてください。
# MAGIC
# MAGIC 「エージェントの精度改善をしたい。エクスペリメント(agentops_traces)とエージェント(app/agent_v1.py)、ツール(app/tools.py)などを分析して、改善案を出して。agent_v2.pyには答えが書いてあるから読まないで。」
