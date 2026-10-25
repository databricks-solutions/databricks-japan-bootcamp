# Databricks notebook source
# MAGIC %md
# MAGIC # 00. 設定（ほかのノートブックから `%run ./00_設定` で読み込む）
# MAGIC
# MAGIC 名前や使うモデルを、ここにまとめています。**下の「書き換える設定」の `CATALOG` だけを、ご自身の環境に合わせて書き換えてください。** ほかのノートブックは変更不要です。
# MAGIC
# MAGIC - スキーマやアプリの名前には、ユーザー名が自動で付きます（同じワークスペースを複数人で使っても、名前がぶつからない）
# MAGIC - AI Search のエンドポイントは、同じワークスペースの参加者で共有します（`01_準備` で、なければ作る）
# MAGIC - 実行すると、エージェント（`app/`）が読む設定ファイル `app/config.yaml` も書き出されます

# COMMAND ----------

# ===== 書き換える設定 =====
CATALOG = ""                                     # 【必ず書き換える】使うカタログ（事前に用意されているもの）
VS_ENDPOINT = "bootcamp"                         # AI Search のエンドポイント（共有。01_準備 で、なければ作る）

LLM_ENDPOINT = "databricks-claude-sonnet-5-5"            # エージェントが使うモデル
JUDGE_ENDPOINT = "databricks-claude-sonnet-4-5"          # LLM ジャッジ（評価）に使うモデル
EMBEDDING_ENDPOINT = "databricks-qwen3-embedding-0-6b"   # 検索インデックスの埋め込みモデル（日本語対応）
WAREHOUSE_NAME = ""                                      # トレースを読むときに使う SQL ウェアハウス。空なら使えるもの（サーバーレスを優先）を自動で選ぶ
# ===== ここまで =====

# COMMAND ----------

import os
import re

import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

_w = WorkspaceClient()
_user = _w.current_user.me().user_name
_user_key = re.sub(r"[^a-z0-9]+", "-", _user.split("@")[0].lower()).strip("-")[:16].strip("-")   # 参加者ごとに名前を分ける

if not CATALOG:
    raise ValueError("00_設定 の CATALOG に、使うカタログの名前を入れてください")

SCHEMA = f"agentops_{_user_key.replace('-', '_')}"
S = f"{CATALOG}.{SCHEMA}"
VOL = f"/Volumes/{CATALOG}/{SCHEMA}"
_nb_dir = "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1])
NOTEBOOK_DIR = f"/Workspace{_nb_dir}"   # ファイルとして読み書きするときのパス
APP_DIR = f"{NOTEBOOK_DIR}/app"         # デプロイするアプリ（エージェントのコードもここ）

DOC_INDEX = f"{S}.doc_chunks_index"
CASE_INDEX = f"{S}.past_cases_index"
WARMUP_SCHEMA = f"{CATALOG}.workshop_shared"   # AI Search の立ち上げ用のダミーのインデックスを置く場所（参加者で共有。01_準備 で作る）
WARMUP_INDEX = f"{WARMUP_SCHEMA}.warmup_index"
PRODUCT_FUNCTION = f"{S}.get_product_info"
EVAL_DATASET = f"{S}.eval_dataset"
EXPERIMENT = f"{_nb_dir}/agentops_traces"        # MLflow の実験（ノートブックと同じフォルダ）
TRACE_TABLE_PREFIX = "agent"                     # トレースを保存するテーブルの名前の先頭（<スキーマ>.agent_otel_spans など）
TRACE_TABLES = [f"{S}.{TRACE_TABLE_PREFIX}_otel_{t}" for t in ["spans", "logs", "metrics", "annotations"]]
APP_NAME = f"agentops-{_user_key}"[:30].rstrip("-")   # アプリの名前（ワークスペースで一意、30文字まで）

# エージェント（app/tools.py）が読む設定ファイル
with open(f"{APP_DIR}/config.yaml", "w") as f:
    yaml.safe_dump({"llm_endpoint": LLM_ENDPOINT, "doc_index": DOC_INDEX, "case_index": CASE_INDEX,
                    "product_function": PRODUCT_FUNCTION}, f, allow_unicode=True, sort_keys=False)

# トレースを読むときの SQL ウェアハウス（作らない。使えるものを選ぶ）
_whs = list(_w.warehouses.list())
_whs = [x for x in _whs if x.name == WAREHOUSE_NAME] or sorted(_whs, key=lambda x: (not x.enable_serverless_compute, x.name))
WAREHOUSE_ID = _whs[0].id if _whs else ""
if WAREHOUSE_ID:
    os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = WAREHOUSE_ID

try:   # カタログがあれば作らない（Default Storage のワークスペースでは、IF NOT EXISTS でもカタログの作成が失敗するため）
    _w.catalogs.get(CATALOG)
except NotFound:
    try:   # カタログがなければ作る（作る権限がなければ、管理者に依頼する）
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    except Exception as e:
        raise RuntimeError(f"カタログ {CATALOG} がなく、作る権限もありません。管理者に、カタログの作成と USE CATALOG・CREATE SCHEMA の付与を依頼してください") from e
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {S}")
spark.sql(f"USE SCHEMA {SCHEMA}")


def use_experiment():
    """MLflow の実験を使う。トレースは Unity Catalog のテーブルに保存する（初回だけ実験とテーブルを作る）。

    MLflow 3.14 以上が必要なので、%pip で入れたノートブック（04〜07）から呼ぶ。
    """
    import mlflow
    from mlflow.entities.trace_location import UnityCatalog
    if not WAREHOUSE_ID:
        raise RuntimeError("使える SQL ウェアハウスがありません。管理者に、SQL ウェアハウスと CAN USE の付与を依頼してください")
    mlflow.set_tracking_uri("databricks")
    return mlflow.set_experiment(experiment_name=EXPERIMENT, trace_location=UnityCatalog(
        catalog_name=CATALOG, schema_name=SCHEMA, table_prefix=TRACE_TABLE_PREFIX))


print(f"""設定を読み込みました
  スキーマ        : {S}
  AI Search       : {VS_ENDPOINT}
  MLflow の実験   : {EXPERIMENT}（トレースは {S}.{TRACE_TABLE_PREFIX}_otel_* に保存）
  アプリ          : {APP_NAME}
  SQL ウェアハウス: {WAREHOUSE_ID or '（なし）'}""")
