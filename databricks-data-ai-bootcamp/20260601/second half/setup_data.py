# Databricks notebook source
# MAGIC %md
# MAGIC # 後半ハンズオン セットアップ
# MAGIC
# MAGIC このノートブックを **「すべて実行」** すると、後半ハンズオン（Lakeflow Designer 名寄せ）で使う
# MAGIC 2 つのテーブルが、あなたの `workspace` カタログに作成されます。
# MAGIC
# MAGIC | テーブル | 内容 | 行数 |
# MAGIC |---|---|---|
# MAGIC | `workspace.bootcamp_tokyo.dirty_companies` | 取引データ（取引先名に表記揺れ・汚染あり） | 3,856 |
# MAGIC | `workspace.bootcamp_tokyo.master_companies` | 正式取引先マスタ | 25 |
# MAGIC
# MAGIC 実行後、Lakeflow Designer の Source で上記テーブルを選択できます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定

# COMMAND ----------

CATALOG = "workspace"
SCHEMA = "bootcamp_tokyo"

# このノートブックと同じ Git フォルダ内の data ディレクトリ
# （リポジトリのスパースチェックアウト構成に合わせて相対パスで取得）
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
# MAGIC ## dirty_companies テーブル作成

# COMMAND ----------

df_dirty = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(f"file:{DATA_DIR}/dirty_companies.csv")
)
df_dirty.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dirty_companies")
print(f"✅ {CATALOG}.{SCHEMA}.dirty_companies : {df_dirty.count()} 行")

# COMMAND ----------

# MAGIC %md
# MAGIC ## master_companies テーブル作成

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

# dirty_companies
spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.dirty_companies IS
'各部署（営業/経理/サポート）から集めた取引データ。company_name は表記揺れ・担当者名混入・NULL 系の汚染があり、AI で正式マスタへ名寄せが必要。2025-01 〜 2026-03 の 15 ヶ月分。'
""")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.dirty_companies ALTER COLUMN company_name COMMENT '取引先名（表記揺れあり、例: (株)ABC商事 / エービーシー商事 / ABC商事 田中様）'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.dirty_companies ALTER COLUMN department COMMENT 'データ入力した部署'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.dirty_companies ALTER COLUMN transaction_date COMMENT '取引日'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.dirty_companies ALTER COLUMN amount COMMENT '取引金額（円）'")

# master_companies
spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.master_companies IS
'取引先の正式マスタテーブル。official_name が公式名称。名寄せの参照先として利用する。'
""")
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
for t in ["dirty_companies", "master_companies"]:
    cnt = spark.table(f"{CATALOG}.{SCHEMA}.{t}").count()
    print(f"  {CATALOG}.{SCHEMA}.{t} : {cnt} 行")

print()
print("=== dirty_companies サンプル（表記揺れを確認）===")
display(
    spark.sql(f"SELECT company_name, department, transaction_date, amount FROM {CATALOG}.{SCHEMA}.dirty_companies LIMIT 20")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## セットアップ完了 🎉
# MAGIC
# MAGIC これで後半ハンズオンの準備ができました。
# MAGIC
# MAGIC Lakeflow Designer の Source 演算子で以下を選択してください:
# MAGIC - `workspace` → `bootcamp_tokyo` → `dirty_companies`
# MAGIC - `workspace` → `bootcamp_tokyo` → `master_companies`
