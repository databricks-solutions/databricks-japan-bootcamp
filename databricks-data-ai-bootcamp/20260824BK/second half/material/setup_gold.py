# Databricks notebook source
# MAGIC %md
# MAGIC # 【リカバリー用】完成テーブルのセットアップ
# MAGIC
# MAGIC ハンズオンで Lakeflow Designer での **Join・集計・ランキング作成が時間内に終わらなかった方向け**のノートブックです。
# MAGIC
# MAGIC このノートブックを **「すべて実行」** すると、完成済みの結果テーブル
# MAGIC `workspace.bootcamp_tokyo.company_sales_ranked`（取引先別の売上ランキング）が作成されます。
# MAGIC
# MAGIC これを実行すれば、Designer のパイプラインが未完成でも、
# MAGIC **後半（メトリクスビュー / Genie / ダッシュボード）のパートに合流**できます。
# MAGIC
# MAGIC > 💡 ハンズオンを最後まで自力で完了できた方は、このノートブックは実行不要です。
# MAGIC > 前提: `setup_data` を先に実行し、`raw_transactions` と `master_companies` が作成済みであること。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定
# MAGIC
# MAGIC `CATALOG` は環境に合わせて変更してください（Free Edition 想定: `workspace`）。

# COMMAND ----------

CATALOG = "workspace"          # ← 環境に合わせて変更（FE-VM検証時は itoen_demo_catalog）
SCHEMA = "bootcamp_tokyo"

print(f"カタログ : {CATALOG}")
print(f"スキーマ : {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 完成テーブルの作成
# MAGIC
# MAGIC ハンズオンで Designer を使って手作業で組む処理を、SQL でまとめて実行します。
# MAGIC - `raw_transactions` と `master_companies` を **master_id で Join**
# MAGIC - 取引先ごとに **売上を合計**（`total_revenue`）
# MAGIC - 売上の多い順に **ランキング**（`rank`）を付与

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.company_sales_ranked AS
SELECT
    m.master_id,
    m.official_name,
    SUM(t.amount) AS total_revenue,
    RANK() OVER (ORDER BY SUM(t.amount) DESC) AS rank
FROM {CATALOG}.{SCHEMA}.raw_transactions t
INNER JOIN {CATALOG}.{SCHEMA}.master_companies m
    ON t.master_id = m.master_id
GROUP BY m.master_id, m.official_name
""")

cnt = spark.table(f"{CATALOG}.{SCHEMA}.company_sales_ranked").count()
print(f"✅ {CATALOG}.{SCHEMA}.company_sales_ranked : {cnt} 行")

# COMMAND ----------

# MAGIC %md
# MAGIC ## テーブル・列コメントを付与（Genie が理解するために）

# COMMAND ----------

spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.company_sales_ranked IS
'取引先別の売上ランキング（完成テーブル）。raw_transactions と master_companies を master_id で結合し、取引先ごとに売上を合計して順位を付けたもの。'
""")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.company_sales_ranked ALTER COLUMN master_id COMMENT '取引先ID'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.company_sales_ranked ALTER COLUMN official_name COMMENT '取引先の正式名称'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.company_sales_ranked ALTER COLUMN total_revenue COMMENT '取引先ごとの売上合計（円）'")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.company_sales_ranked ALTER COLUMN rank COMMENT '売上の多い順の順位（1位が最上位）'")
print("✅ コメントを付与しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認 ─ トップ取引先ランキング

# COMMAND ----------

display(spark.sql(f"""
SELECT rank, official_name, total_revenue
FROM {CATALOG}.{SCHEMA}.company_sales_ranked
ORDER BY rank
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## リカバリー完了 🎉
# MAGIC
# MAGIC `{CATALOG}.{SCHEMA}.company_sales_ranked` が作成されました。
# MAGIC これで後半のパートに合流できます。
