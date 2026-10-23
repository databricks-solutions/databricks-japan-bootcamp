# Databricks notebook source
# MAGIC %md
# MAGIC # 04. エージェントを動かし、トレースで動きを見る（約7分）
# MAGIC
# MAGIC | # | やること | 使う機能 |
# MAGIC |---|---|---|
# MAGIC | 1 | アプリの作成を先に始めておく（起動に時間がかかるため） | Databricks Apps |
# MAGIC | 2 | エージェントのコードを読む | LangGraph・MCP |
# MAGIC | 3 | オペレーターからの相談を1件入れて、回答とトレースを見る | MLflow Tracing |
# MAGIC
# MAGIC エージェントのコードは、このフォルダの `app/` にあります。**ここで評価したコードが、そのまま 07 でアプリとしてデプロイされます。**
# MAGIC
# MAGIC > **注**: 今回は AgentOps に主眼をおくため、エージェントやアプリは弊社で用意した簡易的なサンプルのコードを利用します。なお、今回のサンプルコードはハンズオンでの簡便性を優先しており、一部レガシーな手法が含まれています。今後カスタムのエージェントを開発する場合は、ぜひ [こちらのドキュメント](https://docs.databricks.com/aws/ja/agents/) を参考にして、Agent Bricks をご活用ください。

# COMMAND ----------

# MAGIC %md
# MAGIC ### このノートブックで動かすエージェント（`02_概要` と同じ図）

# COMMAND ----------

# 図の HTML は diagrams.py にある
from diagrams import agent_flow_html

displayHTML(agent_flow_html())

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]==3.17.1" "databricks-langchain==0.21.0" "databricks-mcp==0.9.2" "langgraph>=1.1" "langchain>=1.0" "databricks-sdk>=0.124.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

# トレースの送り先の実験（トレースは Unity Catalog のテーブルに保存される）
experiment = use_experiment()
print(experiment.experiment_id, experiment.trace_location.full_otel_spans_table_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. アプリの作成を先に始めておく
# MAGIC アプリの計算資源の起動には2〜3分かかるので、ここで作成だけ始めておきます（デプロイは 07 で行います）。
# MAGIC アプリには、使うもの（モデル・実験・インデックス・UC関数・トレースのテーブル）を **リソース** として宣言します。宣言すると、アプリのサービスプリンシパルに必要な権限が自動で付きます。

# COMMAND ----------

from apps_helper import app_spec, create_app

APP_SPEC = app_spec(APP_NAME, experiment.experiment_id, LLM_ENDPOINT, DOC_INDEX, CASE_INDEX, PRODUCT_FUNCTION, TRACE_TABLES)
create_app(_w, APP_SPEC)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. エージェントのコードを読む
# MAGIC
# MAGIC | ファイル | 内容 |
# MAGIC |---|---|
# MAGIC | `app/tools.py` | ツール: 製品情報の照会（UC関数を **MCP** で呼ぶ）、文書・過去事例の検索（**AI Search**） |
# MAGIC | `app/agent_v1.py` | 初版のエージェント。LangGraph の `create_agent` に、モデル（Claude）・ツール・システムプロンプトを渡すだけ |
# MAGIC | `app/agent_v2.py` | 改善版（06 で使う） |
# MAGIC
# MAGIC 左のファイルの一覧から `app/agent_v1.py` を開いてみてください。システムプロンプトは2行だけです。

# COMMAND ----------

import sys

sys.path.insert(0, APP_DIR)   # app/ のコードを読み込めるように
import agent_v1
from tools import to_text

print(agent_v1.SYSTEM_PROMPT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 相談を1件入れて、回答とトレースを見る
# MAGIC オペレーターが、お客様から聞いた内容をそのまま文章で入れる想定です。実行すると、セルの下に **トレース** が表示されます。
# MAGIC どのツールがどの順で呼ばれ、どの型番の文書が検索されたかを確かめてください。

# COMMAND ----------

agent = agent_v1.build_agent()   # ノートブックを実行している人の権限で動く


def ask(question: str) -> None:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    print(to_text(result["messages"][-1].content))


ask("炊飯器に E-21 と表示されて炊けない、というお問い合わせです。製造番号は RC6-2509A-00321、購入は2025年10月5日とのことです。")

# COMMAND ----------

# MAGIC %md
# MAGIC ほかの相談も試してみてください（文章を書き換えて実行します）。

# COMMAND ----------

ask("お客様からのお電話です。2026年8月3日に購入された炊飯器が、炊いている途中で電源が切れてしまうそうです。製造番号は RC5-2604B-00871 です。")

# COMMAND ----------

# MAGIC %md
# MAGIC トレースは、Unity Catalog の Delta テーブルに保存されています。SQL でそのまま集計できます。

# COMMAND ----------

display(spark.sql(f"""
  SELECT name, count(*) AS spans
  FROM {S}.{TRACE_TABLE_PREFIX}_otel_spans
  GROUP BY name ORDER BY spans DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC → `05_評価` で、評価データを使って初版の品質を数値にします（改善は `06_改善`）。
