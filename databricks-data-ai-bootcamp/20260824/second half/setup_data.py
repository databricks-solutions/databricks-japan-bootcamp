# Databricks notebook source
# MAGIC %md
# MAGIC # 後半ハンズオン セットアップ
# MAGIC
# MAGIC このノートブックを **「すべて実行」** すると、後半ハンズオン（Lakeflow Designer で取引先別売上ランキングを作る）
# MAGIC で使う 2 つのテーブルが、カタログに作成されます。
# MAGIC
# MAGIC | テーブル | 内容 | 行数 |
# MAGIC |---|---|---|
# MAGIC | `raw_transactions` | 取引明細（基幹システム出力・取引先は master_id のみ） | 93 |
# MAGIC | `master_companies` | 取引先の正式マスタ（正式名称・業界） | 25 |
# MAGIC
# MAGIC 実行後、Lakeflow Designer の Source で上記テーブルを選択できます。
# MAGIC ハンズオンでは 2 つを **master_id で Join** し、取引先別に集計してランキングを作ります。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定
# MAGIC
# MAGIC `CATALOG` は環境に合わせて変更してください。
# MAGIC - Free Edition / 本番想定: `workspace`
# MAGIC - FE-VM（伊藤園デモ環境）で検証する場合: `itoen_demo_catalog`

# COMMAND ----------

CATALOG = "workspace"          # ← 環境に合わせて変更（FE-VM検証時は itoen_demo_catalog）
SCHEMA = "bootcamp_tokyo"

# このノートブックと同じ Git フォルダ内の data ディレクトリ
import os
NOTEBOOK_DIR = os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
)
DATA_DIR = f"/Workspace{NOTEBOOK_DIR}/data"

print(f"カタログ : {CATALOG}")
print(f"スキーマ : {SCHEMA}")
print(f"データ   : {DATA_DIR}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマ作成

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ スキーマ {CATALOG}.{SCHEMA} を準備しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## raw_transactions テーブル作成（取引明細）

# COMMAND ----------

df_tx = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(f"file:{DATA_DIR}/raw_transactions.csv")
)
df_tx.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.raw_transactions")
print(f"✅ {CATALOG}.{SCHEMA}.raw_transactions : {df_tx.count()} 行")

# COMMAND ----------

# MAGIC %md
# MAGIC ## master_companies テーブル作成（取引先マスタ）

# COMMAND ----------

df_master = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(f"file:{DATA_DIR}/master_companies.csv")
)
df_master.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.master_companies")
print(f"✅ {CATALOG}.{SCHEMA}.master_companies : {df_master.count()} 行")

# COMMAND ----------

# MAGIC %md
# MAGIC ## テーブル・列コメントを付与（Genie Code が文脈を理解するために重要）

# COMMAND ----------

# raw_transactions
spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.raw_transactions IS
'基幹システムから出力された取引明細。取引先は master_id のみで、正式名称・業界は master_companies を参照する必要がある。2026-03 の 1 ヶ月分。'
""")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.raw_transactions ALTER COLUMN transaction_id COMMENT '取引ID'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.raw_transactions ALTER COLUMN master_id COMMENT '取引先ID（master_companies.master_id と対応。これで結合する）'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.raw_transactions ALTER COLUMN department COMMENT 'データ入力した部署'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.raw_transactions ALTER COLUMN transaction_date COMMENT '取引日'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.raw_transactions ALTER COLUMN amount COMMENT '取引金額（円）'")

# master_companies
spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.master_companies IS
'取引先の正式マスタテーブル。master_id で取引明細（raw_transactions）と結合する。official_name が公式名称。'
""")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.master_companies ALTER COLUMN master_id COMMENT '取引先ID（raw_transactions.master_id と対応）'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.master_companies ALTER COLUMN official_name COMMENT '取引先の正式名称'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.master_companies ALTER COLUMN industry COMMENT '業界'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.master_companies ALTER COLUMN region COMMENT '本社所在地'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.master_companies ALTER COLUMN established_year COMMENT '設立年'")

print("✅ コメントを付与しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

print("=== 作成されたテーブル ===")
for t in ["raw_transactions", "master_companies"]:
    cnt = spark.table(f"{CATALOG}.{SCHEMA}.{t}").count()
    print(f"  {CATALOG}.{SCHEMA}.{t} : {cnt} 行")

print()
print("=== raw_transactions サンプル（取引先は master_id のみ）===")
display(
    spark.sql(f"SELECT transaction_id, master_id, department, transaction_date, amount FROM {CATALOG}.{SCHEMA}.raw_transactions LIMIT 10")
)

print()
print("=== master_companies サンプル（master_id → 正式名称）===")
display(
    spark.sql(f"SELECT master_id, official_name, industry, region FROM {CATALOG}.{SCHEMA}.master_companies LIMIT 10")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## （参考）ハンズオン完成時の答え合わせ用
# MAGIC
# MAGIC 参加者が Designer で作る出力（取引先別売上ランキング）は、以下と一致するはずです。
# MAGIC このセルは講師の確認用です（ハンズオンでは実行しません）。

# COMMAND ----------

display(spark.sql(f"""
SELECT m.master_id, m.official_name, SUM(t.amount) AS total_revenue,
       RANK() OVER (ORDER BY SUM(t.amount) DESC) AS rank
FROM {CATALOG}.{SCHEMA}.raw_transactions t
INNER JOIN {CATALOG}.{SCHEMA}.master_companies m ON t.master_id = m.master_id
GROUP BY m.master_id, m.official_name
ORDER BY total_revenue DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## セットアップ完了 🎉
# MAGIC
# MAGIC これで後半ハンズオンの準備ができました。
# MAGIC
# MAGIC Lakeflow Designer の Source 演算子で以下を選択してください:
# MAGIC - `{CATALOG}` → `bootcamp_tokyo` → `raw_transactions`
# MAGIC - `{CATALOG}` → `bootcamp_tokyo` → `master_companies`
