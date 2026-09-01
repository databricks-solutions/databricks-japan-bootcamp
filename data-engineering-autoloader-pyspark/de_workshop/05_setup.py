# Databricks notebook source
# MAGIC %md
# MAGIC # 05. 初期セットアップ
# MAGIC
# MAGIC 各参加者が最初に一度だけ実行する初期セットアップ。以降の Bronze / Silver / Gold ノートブックは、
# MAGIC このノートブックを `%run` でインポートして共通変数を引き継ぐ。
# MAGIC
# MAGIC このノートブックが行うこと:
# MAGIC - 共通変数の定義（カタログ・スキーマ・共有 Volume パスなど）
# MAGIC - 自分専用スキーマと専用チェックポイント Volume の作成
# MAGIC - 共有 Volume からマスターテーブルを取り込み（`replace_master_tables` で再作成を制御）

# COMMAND ----------

# MAGIC %md
# MAGIC ## 変数定義

# COMMAND ----------

# 各参加者が自分の識別子に書き換える
user_name = "ここをご自身の分かりやすい名前をここに入れてください"

# 管理者から指定されるワークショップ用カタログ名に書き換える
catalog = "ここを管理者から指定されるワークショップ用カタログ名に書き換えてください"

# COMMAND ----------

# 以下は変更不要

from pyspark.sql import functions as F

schema  = f"dew_{user_name}"                           # 参加者スキーマ（接頭辞 dew_）
bp = f"{catalog}.{schema}"

shared_schema   = "de_workshop_shared"
shared_landing  = f"/Volumes/{catalog}/{shared_schema}/landing"   # 共有（全員が直接読み取り）
shared_master   = f"/Volumes/{catalog}/{shared_schema}/master"    # 共有（マスター Parquet）
checkpoint_base = f"/Volumes/{catalog}/{schema}/checkpoints"      # 参加者専用

# ★マスターテーブルの再作成制御
#   True : 常にマスターテーブルを作り直す
#   False: 存在しないマスターテーブルのみ作成（デフォルト）
replace_master_tables = False

print(f"catalog={catalog}, schema={schema}")
print(f"checkpoint_base={checkpoint_base}, replace_master_tables={replace_master_tables}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマ・チェックポイント Volume の作成
# MAGIC 自分専用のスキーマと、Auto Loader のチェックポイントを置く専用 Volume を作成する。

# COMMAND ----------

# 自分専用スキーマと専用チェックポイント Volume を作成
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.checkpoints")
print(f"作成: スキーマ {bp} / Volume {catalog}.{schema}.checkpoints")

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターテーブルの取り込み
# MAGIC 共有 master Volume から 3 マスターを読み、自分のスキーマに Bronze マスターテーブルとして保存する。
# MAGIC `replace_master_tables=False` の場合は、未作成のマスターのみ作成する（重複実行を防ぐ）。

# COMMAND ----------

def _table_exists(table_name: str) -> bool:
    # スキーマ内に対象テーブルが存在するか確認
    return spark.catalog.tableExists(f"{bp}.{table_name}")

def load_master(name: str):
    target = f"bronze_{name}"
    # replace=False かつ既存ならスキップ（重複実行防止）
    if (not replace_master_tables) and _table_exists(target):
        print(f"スキップ（既存）: {target}")
        return
    # 共有 Volume から直接読み取り、自分のスキーマにマネージドテーブルとして保存
    (spark.read.parquet(f"{shared_master}/{name}/")
        .write.mode("overwrite").saveAsTable(f"{bp}.{target}"))
    print(f"作成: {target} = {spark.table(f'{bp}.{target}').count():,} 件")

for m in ["m_customers", "m_merchants", "m_payment_methods"]:
    load_master(m)

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターへの PK 制約付与
# MAGIC 後続の Silver / Gold で FK 参照するため、マスターに主キー制約を付与する（未設定時のみ）。

# COMMAND ----------

def _pk_exists(table_name: str) -> bool:
    # 既に PK 制約が存在するか確認（子 FK があると DROP できないため、存在時は触らない）
    df = spark.sql(f"""
        SELECT 1 FROM {catalog}.information_schema.table_constraints
        WHERE table_schema='{schema}' AND table_name='{table_name}'
          AND constraint_type='PRIMARY KEY' LIMIT 1""")
    return df.count() > 0

def add_pk(table_name: str, pk_col: str):
    full = f"{bp}.{table_name}"
    # 既に PK があれば何もしない（マスターは Silver/Gold から FK 参照されるため drop 不可）
    if _pk_exists(table_name):
        print(f"PK 既存（スキップ）: {full}")
        return
    # PK 対象列を NOT NULL 化してから PRIMARY KEY を宣言
    spark.sql(f"ALTER TABLE {full} ALTER COLUMN {pk_col} SET NOT NULL")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {table_name}_pk PRIMARY KEY({pk_col})")
    print(f"PK: {full}({pk_col})")

add_pk("bronze_m_customers", "customer_id")
add_pk("bronze_m_merchants", "merchant_id")
add_pk("bronze_m_payment_methods", "method_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ 初期セットアップ完了 — 現在の状態
# MAGIC
# MAGIC 初期セットアップが完了した。現時点で作成されているオブジェクトは以下のとおり。
# MAGIC
# MAGIC ```
# MAGIC 【共有（講師が事前準備・全員が参照）】
# MAGIC   Volume: <ワークショップ用カタログ名>.de_workshop_shared.master   ← マスター Parquet
# MAGIC   Volume: <ワークショップ用カタログ名>.de_workshop_shared.landing  ← ファクト Parquet
# MAGIC
# MAGIC 【自分専用スキーマ  <ワークショップ用カタログ名>.dew_<user_name>】
# MAGIC   ├─ Volume: checkpoints                 ← Auto Loader のチェックポイント（この後 Bronze で使用）
# MAGIC   ├─ TABLE : bronze_m_customers  (PK)    ← 会員マスター（共有 master から取込済み）
# MAGIC   ├─ TABLE : bronze_m_merchants  (PK)    ← 加盟店マスター（取込済み）
# MAGIC   └─ TABLE : bronze_m_payment_methods (PK) ← 決済手段マスター（取込済み）
# MAGIC
# MAGIC   ※ ファクトの Bronze テーブル（bronze_t_*）は、次の Bronze ノートブックで
# MAGIC      Auto Loader が共有 landing Volume から取り込んで作成する。
# MAGIC ```
# MAGIC
# MAGIC ### この後の流れ
# MAGIC | ノートブック | 作成されるもの |
# MAGIC |---|---|
# MAGIC | **10 Bronze** | `bronze_t_payments` 等のファクト（Auto Loader で取込） |
# MAGIC | **20 Silver** | `silver_payments` 等（マスター結合＋クレンジング） |
# MAGIC | **30 Gold** | `gold_customer_summary` 等（集計） |
# MAGIC
# MAGIC 各ノートブックの冒頭では、このセットアップノートブックを `%run ./05_setup` で読み込み、
# MAGIC ここで定義した変数（`catalog` / `schema` / `bp` / `shared_landing` / `checkpoint_base` など）を再利用する。

# COMMAND ----------

print("✅ 初期セットアップ完了")
print(f"  スキーマ: {bp}")
for t in ["bronze_m_customers", "bronze_m_merchants", "bronze_m_payment_methods"]:
    print(f"  {t}: {spark.table(f'{bp}.{t}').count():,} 件")