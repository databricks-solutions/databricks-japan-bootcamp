# Databricks notebook source
# MAGIC %md
# MAGIC # 99. クリーンアップ: 自分が作ったものを削除する
# MAGIC
# MAGIC `00_設定` の名前をもとに、ワークショップで作ったものを削除します。**削除したものは元に戻せません。**
# MAGIC
# MAGIC | 削除するもの | 作ったノートブック |
# MAGIC |---|---|
# MAGIC | アプリ（`APP_NAME`） | 04・07 |
# MAGIC | 検索インデックス（`doc_chunks_index` / `past_cases_index`） | 03 |
# MAGIC | UC関数（`get_product_info`）・テーブル・Volume | 01・03・05 |
# MAGIC | MLflow の実験と、トレースのテーブル（`agent_otel_*` など） | 04〜07 |
# MAGIC | 設定ファイル `app/config.yaml` | 00_設定 |
# MAGIC
# MAGIC AI Search のエンドポイントと、立ち上げ用のダミーのインデックス（`workshop_shared`）は参加者で共有しているので、削除しません。
# MAGIC
# MAGIC **実行のしかた**: 下のセルの `CONFIRM_DELETE` を `True` にしてから、すべてのセルを実行します。スキーマごと削除する場合は `DROP_SCHEMA` も `True` にします。

# COMMAND ----------

CONFIRM_DELETE = False   # True にすると削除する
DROP_SCHEMA = False      # True にすると、最後にスキーマごと削除する

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

if not CONFIRM_DELETE:
    dbutils.notebook.exit("CONFIRM_DELETE が False のため、何も削除していません")
print(f"削除を始めます（スキーマ: {S}、スキーマごと削除: {DROP_SCHEMA}）")

# COMMAND ----------

import os

import pandas as pd
from databricks.sdk.errors import NotFound

results = []


def remove(kind, name, fn):
    try:
        fn()
        results.append((kind, name, "削除した"))
    except NotFound:
        results.append((kind, name, "なかった"))
    except Exception as e:
        msg = str(e)
        results.append((kind, name, "なかった" if "does not exist" in msg or "not found" in msg.lower() else f"失敗: {msg[:150]}"))


remove("アプリ", APP_NAME, lambda: _w.apps.delete(APP_NAME))
for idx in [DOC_INDEX, CASE_INDEX]:
    remove("検索インデックス", idx, lambda idx=idx: _w.vector_search_indexes.delete_index(idx))
remove("UC関数", PRODUCT_FUNCTION, lambda: spark.sql(f"DROP FUNCTION {PRODUCT_FUNCTION}"))

trace_tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {S} LIKE '{TRACE_TABLE_PREFIX}_*'").collect()]
for t in ["eval_dataset", "doc_chunks", "past_cases", "docs_parsed", "products", "production_lots", "repair_requests"] + trace_tables:
    remove("テーブル", f"{S}.{t}", lambda t=t: spark.sql(f"DROP TABLE {S}.{t}") if not t.endswith(("_metadata", "_unified"))
           else spark.sql(f"DROP VIEW IF EXISTS {S}.{t}"))
for v in ["raw_files", "docs"]:
    remove("Volume", f"{S}.{v}", lambda v=v: spark.sql(f"DROP VOLUME {S}.{v}"))


def _delete_experiment():
    exp = _w.experiments.get_by_name(EXPERIMENT).experiment
    _w.experiments.delete_experiment(exp.experiment_id)


remove("MLflow の実験", EXPERIMENT, _delete_experiment)
remove("設定ファイル", "app/config.yaml", lambda: os.remove(f"{APP_DIR}/config.yaml"))
if DROP_SCHEMA:
    remove("スキーマ", S, lambda: spark.sql(f"DROP SCHEMA {S} CASCADE"))

display(pd.DataFrame(results, columns=["種類", "名前", "結果"]))
