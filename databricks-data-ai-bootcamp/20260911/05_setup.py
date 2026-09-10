# Databricks notebook source
# MAGIC %md
# MAGIC # 05. 初期セットアップ（Free Edition 版）
# MAGIC
# MAGIC 最初に一度だけ実行する初期セットアップ。以降の Bronze / Silver / Gold ノートブックは、
# MAGIC このノートブックを `%run` でインポートして共通変数を引き継ぐ。
# MAGIC
# MAGIC **Databricks Free Edition** での単独実行を前提とし、カタログ・スキーマを固定する。
# MAGIC 共有カタログや参加者グループは使わず、すべて自分の `workspace.de_workshop` に作成する。
# MAGIC
# MAGIC このノートブックが行うこと:
# MAGIC - 共通変数の定義（カタログ `workspace` / スキーマ `de_workshop` / Volume パス）
# MAGIC - スキーマと 3 つのマネージド Volume（`landing` / `master` / `checkpoints`）の作成
# MAGIC - `admin/00` が生成した `master` Volume のマスター Parquet を Bronze マスターテーブルとして取り込み
# MAGIC
# MAGIC > **事前に `admin/00_setup_and_generate_initial_data` を実行**して、`master` / `landing` Volume に
# MAGIC > マスター・ファクトの Parquet を生成しておくこと。このノートブックはそのデータを前提にマスターを取り込む。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 変数定義（Free Edition 固定値）

# COMMAND ----------

from pyspark.sql import functions as F

# Free Edition の既定カタログ。スキーマは固定。
catalog = "workspace"
schema  = "de_workshop"
bp = f"{catalog}.{schema}"

# 自分のスキーマ配下のマネージド Volume（S3 等の外部ストレージは使わない）
landing         = f"/Volumes/{catalog}/{schema}/landing"       # ファクト Parquet（admin/00 が生成）
master          = f"/Volumes/{catalog}/{schema}/master"        # マスター Parquet（admin/00 が生成）
checkpoint_base = f"/Volumes/{catalog}/{schema}/checkpoints"   # Auto Loader チェックポイント

# ★マスターテーブルの再作成制御
#   True : 常に作り直す / False: 未作成のみ作成（デフォルト）
replace_master_tables = False

print(f"catalog={catalog}, schema={schema}")
print(f"landing={landing}")
print(f"master={master}")
print(f"checkpoint_base={checkpoint_base}, replace_master_tables={replace_master_tables}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマと 3 つのマネージド Volume を作成
# MAGIC `landing`（ファクト）/ `master`（マスター）/ `checkpoints`（Auto Loader 用）を作成する。
# MAGIC `landing` と `master` には admin/00 がデータを生成する。

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
for v in ["landing", "master", "checkpoints"]:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{v}")
print(f"作成: スキーマ {bp} / Volume landing・master・checkpoints")
print("——— データは admin/00 が master/ と landing/ 配下に生成します（先に admin/00 を実行）———")

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターテーブルの取り込み
# MAGIC `admin/00` が `master` Volume に生成したマスター Parquet を読み、自分のスキーマに Bronze マスターテーブルとして保存する。
# MAGIC （まだアップロードしていない場合はスキップし、アップロード後に再実行する）

# COMMAND ----------

def _table_exists(table_name: str) -> bool:
    return spark.catalog.tableExists(f"{bp}.{table_name}")

def _has_files(path: str) -> bool:
    # Volume 配下にファイルが存在するか（未アップロード判定）
    try:
        return len([f for f in dbutils.fs.ls(path) if not f.name.startswith("_")]) > 0
    except Exception:
        return False

def load_master(name: str):
    target = f"bronze_{name}"
    if (not replace_master_tables) and _table_exists(target):
        print(f"スキップ（既存）: {target}")
        return
    src = f"{master}/{name}/"
    if not _has_files(src):
        print(f"⚠ 未生成: {src} — admin/00 を実行してから再実行してください")
        return
    (spark.read.parquet(src)
        .write.mode("overwrite").saveAsTable(f"{bp}.{target}"))
    print(f"作成: {target} = {spark.table(f'{bp}.{target}').count():,} 件")

for m in ["m_customers", "m_merchants", "m_payment_methods"]:
    load_master(m)

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターへの PK 制約付与
# MAGIC 後続の Silver / Gold で FK 参照するため、マスターに主キー制約を付与する（テーブル作成済みかつ未設定時のみ）。

# COMMAND ----------

def _pk_exists(table_name: str) -> bool:
    df = spark.sql(f"""
        SELECT 1 FROM {catalog}.information_schema.table_constraints
        WHERE table_schema='{schema}' AND table_name='{table_name}'
          AND constraint_type='PRIMARY KEY' LIMIT 1""")
    return df.count() > 0

def add_pk(table_name: str, pk_col: str):
    full = f"{bp}.{table_name}"
    if not _table_exists(table_name):
        print(f"スキップ（テーブル未作成）: {full} — admin/00 を実行してから再実行してください")
        return
    if _pk_exists(table_name):
        print(f"PK 既存（スキップ）: {full}")
        return
    spark.sql(f"ALTER TABLE {full} ALTER COLUMN {pk_col} SET NOT NULL")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {table_name}_pk PRIMARY KEY({pk_col})")
    print(f"PK: {full}({pk_col})")

add_pk("bronze_m_customers", "customer_id")
add_pk("bronze_m_merchants", "merchant_id")
add_pk("bronze_m_payment_methods", "method_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ 初期セットアップの状態
# MAGIC
# MAGIC ```
# MAGIC 【自分のスキーマ  workspace.de_workshop】
# MAGIC   ├─ Volume : landing      ← admin/00 がファクト Parquet を生成（この後 Bronze で取り込む）
# MAGIC   ├─ Volume : master       ← admin/00 がマスター Parquet を生成（上で取り込み済み）
# MAGIC   ├─ Volume : checkpoints  ← Auto Loader のチェックポイント（Bronze で使用）
# MAGIC   ├─ TABLE  : bronze_m_customers  (PK)
# MAGIC   ├─ TABLE  : bronze_m_merchants  (PK)
# MAGIC   └─ TABLE  : bronze_m_payment_methods (PK)
# MAGIC ```
# MAGIC
# MAGIC | ノートブック | 作成されるもの |
# MAGIC |---|---|
# MAGIC | **10 Bronze** | `bronze_t_*` ファクト（Auto Loader が `landing` から取り込み） |
# MAGIC | **20 Silver** | `silver_*`（マスター結合＋クレンジング） |
# MAGIC | **30 Gold** | `gold_*`（集計） |
# MAGIC
# MAGIC 各ノートブック冒頭で `%run ./05_setup` を実行し、`catalog` / `schema` / `bp` / `landing` / `checkpoint_base` を再利用する。

# COMMAND ----------

print("✅ 初期セットアップ完了")
print(f"  スキーマ: {bp}")
for t in ["bronze_m_customers", "bronze_m_merchants", "bronze_m_payment_methods"]:
    if _table_exists(t):
        print(f"  {t}: {spark.table(f'{bp}.{t}').count():,} 件")
