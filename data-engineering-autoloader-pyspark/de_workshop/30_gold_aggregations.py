# Databricks notebook source
# MAGIC %md
# MAGIC # 30. Gold：集計テーブル群
# MAGIC
# MAGIC Silver から、**顧客別・加盟店別・決済手段別・日次**の集計テーブルを作る。
# MAGIC ダッシュボード・Genie の対象になる。
# MAGIC - テーブル作成時は**リキッドクラスタリング**（フィルタ/結合キーに適用）
# MAGIC - **PK / FK 制約**を付与

# COMMAND ----------

# MAGIC %md
# MAGIC ## 初期セットアップの読み込み
# MAGIC セットアップノートブックを実行し、共通変数を引き継ぐ。

# COMMAND ----------

# MAGIC %run ./05_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold customer_summary：顧客ごとに決済指標を集計
# MAGIC 集計/結合キーである `customer_id` でクラスタリングし、PK と会員マスターへの FK を付与する。

# COMMAND ----------

silver_payments = spark.table(f"{bp}.silver_payments")   # Silver 決済テーブルを読み込み

gold_customer_summary = silver_payments.groupBy("customer_id").agg(   # 顧客単位に集計
    F.count("*").alias("payment_count"),                              # 決済回数
    F.sum("amount").alias("total_amount"),                           # 決済総額
    F.round(F.avg("amount"), 0).alias("avg_amount"),                 # 平均決済額
    F.sum(F.col("is_fraud").cast("int")).alias("fraud_count"),       # 不正件数
    F.round(F.avg(F.col("is_fraud").cast("int")) * 100, 2).alias("fraud_rate_pct"),  # 不正率(%)
    F.max("payment_date").alias("last_payment_date"))               # 最終決済日

# ★clusterBy: 顧客絞り込み/結合に使う customer_id
(gold_customer_summary.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("customer_id")
    .saveAsTable(f"{bp}.gold_customer_summary"))
print(f"gold_customer_summary: {spark.table(f'{bp}.gold_customer_summary').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold merchant_summary：加盟店ごとに集計
# MAGIC 結合キー `merchant_id` でクラスタリングし、PK と加盟店マスターへの FK を付与する。

# COMMAND ----------

gold_merchant_summary = silver_payments.groupBy(
        "merchant_id", "merchant_name", "merchant_category").agg(       # 加盟店単位に集計
    F.count("*").alias("payment_count"),
    F.sum("amount").alias("total_amount"),
    F.round(F.avg("amount"), 0).alias("avg_amount"),
    F.countDistinct("customer_id").alias("unique_customers"),
    F.sum(F.col("is_fraud").cast("int")).alias("fraud_count"),
    F.round(F.avg(F.col("is_fraud").cast("int")) * 100, 2).alias("fraud_rate_pct"))

# ★clusterBy: 加盟店絞り込み/結合に使う merchant_id
(gold_merchant_summary.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("merchant_id")
    .saveAsTable(f"{bp}.gold_merchant_summary"))
print(f"gold_merchant_summary: {spark.table(f'{bp}.gold_merchant_summary').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold payment_method_summary：決済手段種別ごとに集計
# MAGIC ダッシュボードのフィルタに使う `method_type` でクラスタリングし、PK を付与する。

# COMMAND ----------

gold_payment_method_summary = silver_payments.groupBy("method_type").agg(   # 決済手段種別に集計
    F.count("*").alias("payment_count"),
    F.sum("amount").alias("total_amount"),
    F.round(F.avg("amount"), 0).alias("avg_amount"),
    F.countDistinct("customer_id").alias("unique_customers"),
    F.sum(F.col("is_fraud").cast("int")).alias("fraud_count"),
    F.round(F.avg(F.col("is_fraud").cast("int")) * 100, 2).alias("fraud_rate_pct"))

# ★clusterBy: ダッシュボードでフィルタする method_type
(gold_payment_method_summary.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("method_type")
    .saveAsTable(f"{bp}.gold_payment_method_summary"))
print(f"gold_payment_method_summary: {spark.table(f'{bp}.gold_payment_method_summary').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold daily_payment_trend：日付×決済手段で集計（Spark SQL）
# MAGIC PySpark と Spark SQL の使い分けを見せるため Spark SQL で記述。時系列フィルタに使う `payment_date` で `CLUSTER BY`。

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {bp}.gold_daily_payment_trend
CLUSTER BY (payment_date)                              -- ★時系列フィルタに使う payment_date
AS
SELECT payment_date, method_type,
       COUNT(*) AS payment_count,                      -- 決済回数
       SUM(amount) AS total_amount,                    -- 決済総額
       ROUND(AVG(amount), 0) AS avg_amount,            -- 平均決済額
       SUM(CAST(is_fraud AS INT)) AS fraud_count,      -- 不正件数
       ROUND(AVG(CAST(is_fraud AS INT)) * 100, 2) AS fraud_rate_pct  -- 不正率(%)
FROM {bp}.silver_payments
GROUP BY payment_date, method_type
""")
print(f"gold_daily_payment_trend: {spark.table(f'{bp}.gold_daily_payment_trend').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## PK / FK 制約の付与
# MAGIC 各 Gold テーブルに主キーを、集計軸に応じてマスターへの外部キーを付与する。

# COMMAND ----------

def add_pk(table_name: str, pk_cols):
    full = f"{bp}.{table_name}"
    cols = pk_cols if isinstance(pk_cols, list) else [pk_cols]
    for c in cols:
        spark.sql(f"ALTER TABLE {full} ALTER COLUMN {c} SET NOT NULL")               # PK列は NOT NULL 必須
    spark.sql(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS {table_name}_pk")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {table_name}_pk PRIMARY KEY({', '.join(cols)})")
    print(f"PK: {full}({', '.join(cols)})")

def add_fk(table_name: str, fk_col: str, parent_table: str):
    full = f"{bp}.{table_name}"
    cname = f"{table_name}_{fk_col}_fk"
    spark.sql(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS {cname}")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {cname} FOREIGN KEY({fk_col}) REFERENCES {bp}.{parent_table}")
    print(f"FK: {full}.{fk_col} -> {bp}.{parent_table}")

# 主キー
add_pk("gold_customer_summary", "customer_id")
add_pk("gold_merchant_summary", "merchant_id")
add_pk("gold_payment_method_summary", "method_type")
add_pk("gold_daily_payment_trend", ["payment_date", "method_type"])   # 複合主キー

# 外部キー（集計軸のマスターへの参照）
add_fk("gold_customer_summary", "customer_id", "bronze_m_customers")
add_fk("gold_merchant_summary", "merchant_id", "bronze_m_merchants")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {bp} LIKE 'gold_*'"))
display(spark.table(f"{bp}.gold_payment_method_summary"))
print("✅ Gold 作成 完了")