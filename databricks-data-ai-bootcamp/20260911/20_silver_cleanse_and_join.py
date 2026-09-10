# Databricks notebook source
# MAGIC %md
# MAGIC # 20. Silver：クレンジング + マスター結合
# MAGIC
# MAGIC 各ファクトに関連マスターを結合し、クレンジングした Silver テーブルを作る。
# MAGIC - 可読性のため、各ファクト・マスターを**別々の名前付き DataFrame**に読み込んでから結合
# MAGIC - テーブル作成時は**リキッドクラスタリング**（結合キーに適用）
# MAGIC - **PK / FK 制約**を付与

# COMMAND ----------

# MAGIC %md
# MAGIC ## 初期セットアップの読み込み
# MAGIC セットアップノートブックを実行し、共通変数を引き継ぐ。

# COMMAND ----------

# MAGIC %run ./05_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver payments：決済ファクトに 3 マスターを結合しクレンジング
# MAGIC まず決済ファクトと各マスターを**別々の DataFrame**に読み込む。次に結合し、派生列を付与して保存する。
# MAGIC 結合キー `customer_id` でリキッドクラスタリングを設定する。

# COMMAND ----------

# --- Step 1: 各ファクト・マスターをそれぞれ別々の DataFrame に読み込む（可読性のため）---
payments_df = (spark.table(f"{bp}.bronze_t_payments")           # 決済ファクト
                    .dropDuplicates(["payment_id"])                       # 主キーで重複排除
                    .filter(F.col("status").isin("完了", "返金")))        # 有効な決済のみ

customers_df = (spark.table(f"{bp}.bronze_m_customers")         # 会員マスター（必要列のみ）
                     .select("customer_id",
                             F.col("prefecture").alias("customer_prefecture"),
                             "telecom_plan", "avg_monthly_spend",
                             "primary_device_id", "customer_status"))

merchants_df = (spark.table(f"{bp}.bronze_m_merchants")         # 加盟店マスター（必要列のみ）
                     .select("merchant_id",
                             F.col("category").alias("merchant_category"),
                             F.col("prefecture").alias("merchant_prefecture"),
                             "merchant_name"))

methods_df = (spark.table(f"{bp}.bronze_m_payment_methods")     # 決済手段マスター（必要列のみ）
                   .select("method_id", "method_type"))

# --- Step 2: 決済ファクトに 3 マスターを結合（すべて左結合）---
joined_df = (payments_df
             .join(customers_df, on="customer_id", how="left")   # 会員属性を付与
             .join(merchants_df, on="merchant_id", how="left")   # 加盟店属性を付与
             .join(methods_df,   on="method_id",   how="left"))  # 決済手段種別を付与

# --- Step 3: 派生列（クレンジング＋特徴量）を付与 ---
silver_payments = (joined_df
    .withColumn("payment_date", F.to_date("payment_timestamp"))              # 日付
    .withColumn("payment_hour", F.hour("payment_timestamp"))                 # 時間帯
    .withColumn("is_night", F.col("payment_hour").between(2, 5))             # 深夜フラグ
    .withColumn("amount_ratio",                                             # 月間平均比
                F.round(F.col("amount") / (F.col("avg_monthly_spend") / 30), 2))
    .withColumn("is_geo_mismatch",                                          # 決済地と住所の不一致
                F.col("transaction_prefecture") != F.col("customer_prefecture"))
    .withColumn("is_new_device",                                            # 主利用デバイスと不一致
                F.col("device_id") != F.col("primary_device_id")))

# --- Step 4: リキッドクラスタリングを指定してテーブル作成 ---
# ★clusterBy: 下流 Gold の集計/結合キーであり FK 参照キーでもある customer_id を指定
(silver_payments.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("customer_id")
    .saveAsTable(f"{bp}.silver_payments"))
print(f"silver_payments: {spark.table(f'{bp}.silver_payments').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver point_transactions / charges / login_events
# MAGIC いずれも会員マスターを結合し、結合キー `customer_id` でクラスタリングする。

# COMMAND ----------

# --- ポイント取引 ---
points_df = spark.table(f"{bp}.bronze_t_point_transactions").dropDuplicates(["point_txn_id"])
cust_plan_df = spark.table(f"{bp}.bronze_m_customers").select("customer_id", "telecom_plan")
silver_point_transactions = (points_df
    .join(cust_plan_df, on="customer_id", how="left")                       # 会員属性を付与
    .withColumn("txn_date", F.to_date("txn_timestamp"))                     # 日付
    .withColumn("is_expiry", F.col("txn_type") == "失効"))                  # 失効フラグ
(silver_point_transactions.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("customer_id")                                               # ★結合キー
    .saveAsTable(f"{bp}.silver_point_transactions"))
print(f"silver_point_transactions: {spark.table(f'{bp}.silver_point_transactions').count():,} 件")

# --- チャージ ---
charges_df = spark.table(f"{bp}.bronze_t_charges").dropDuplicates(["charge_id"])
cust_plan_df2 = spark.table(f"{bp}.bronze_m_customers").select("customer_id", "telecom_plan")
silver_charges = (charges_df
    .join(cust_plan_df2, on="customer_id", how="left")                      # 会員属性を付与
    .withColumn("charge_date", F.to_date("charge_timestamp"))               # 日付
    .withColumn("is_failed", F.col("status") == "失敗"))                    # 失敗フラグ
(silver_charges.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("customer_id")                                               # ★結合キー
    .saveAsTable(f"{bp}.silver_charges"))
print(f"silver_charges: {spark.table(f'{bp}.silver_charges').count():,} 件")

# --- ログイン ---
logins_df = spark.table(f"{bp}.bronze_t_login_events").dropDuplicates(["login_id"])
cust_geo_df = (spark.table(f"{bp}.bronze_m_customers")
                    .select("customer_id",
                            F.col("prefecture").alias("customer_prefecture"),
                            "primary_device_id"))
silver_login_events = (logins_df
    .join(cust_geo_df, on="customer_id", how="left")                        # 会員属性を付与
    .withColumn("login_date", F.to_date("login_timestamp"))                 # 日付
    .withColumn("is_geo_mismatch", F.col("login_prefecture") != F.col("customer_prefecture"))
    .withColumn("is_new_device",   F.col("device_id") != F.col("primary_device_id")))
(silver_login_events.write.mode("overwrite").option("overwriteSchema", "true")
    .clusterBy("customer_id")                                               # ★結合キー
    .saveAsTable(f"{bp}.silver_login_events"))
print(f"silver_login_events: {spark.table(f'{bp}.silver_login_events').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## PK / FK 制約の付与
# MAGIC 各 Silver テーブルに主キーを、会員・加盟店・決済手段マスターへの外部キーを付与する。

# COMMAND ----------

def add_pk(table_name: str, pk_col: str):
    full = f"{bp}.{table_name}"
    spark.sql(f"ALTER TABLE {full} ALTER COLUMN {pk_col} SET NOT NULL")             # PK列は NOT NULL 必須
    spark.sql(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS {table_name}_pk")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {table_name}_pk PRIMARY KEY({pk_col})")
    print(f"PK: {full}({pk_col})")

def add_fk(table_name: str, fk_col: str, parent_table: str):
    full = f"{bp}.{table_name}"
    cname = f"{table_name}_{fk_col}_fk"
    spark.sql(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS {cname}")
    # FK: 子テーブルの fk_col → 親テーブルの PK を参照
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {cname} FOREIGN KEY({fk_col}) REFERENCES {bp}.{parent_table}")
    print(f"FK: {full}.{fk_col} -> {bp}.{parent_table}")

# 主キー
add_pk("silver_payments", "payment_id")
add_pk("silver_point_transactions", "point_txn_id")
add_pk("silver_charges", "charge_id")
add_pk("silver_login_events", "login_id")

# 外部キー（マスターへの参照）
add_fk("silver_payments", "customer_id", "bronze_m_customers")
add_fk("silver_payments", "merchant_id", "bronze_m_merchants")
add_fk("silver_payments", "method_id",   "bronze_m_payment_methods")
add_fk("silver_point_transactions", "customer_id", "bronze_m_customers")
add_fk("silver_charges", "customer_id", "bronze_m_customers")
add_fk("silver_login_events", "customer_id", "bronze_m_customers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {bp} LIKE 'silver_*'"))
print("✅ Silver 作成 完了")