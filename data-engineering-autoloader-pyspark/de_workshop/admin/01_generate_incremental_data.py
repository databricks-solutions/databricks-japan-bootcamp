# Databricks notebook source
# MAGIC %md
# MAGIC # 01. 増分データ生成（講師用）
# MAGIC
# MAGIC Auto Loader の**増分取り込み**を体験するため、初回ロード後に**全ファクトの追加データ**を
# MAGIC 共有 Volume に **Parquet** で投入する。
# MAGIC
# MAGIC - 追加分は新しい日付範囲（2026-07 月）で生成
# MAGIC - 既存ファイルを上書きしないよう、`batch=<日付>` サブディレクトリに出力
# MAGIC - **マスターは変更しない**。外部キーは既存マスターのキー範囲からのみ採番する

# COMMAND ----------

# MAGIC %md
# MAGIC ## ライブラリのインストール

# COMMAND ----------

# MAGIC %pip install dbldatagen
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## パラメータ設定
# MAGIC **初期生成（NB00）と同じ採番母数**を使うことが重要（新しいマスターキーを作らないため）。

# COMMAND ----------

catalog = "<ワークショップ用カタログ名>"
shared_schema = "de_workshop_shared"
shared_landing = f"/Volumes/{catalog}/{shared_schema}/landing"

# ★NB00 と同じ母数（既存マスターキーの範囲に収めるため必須）
num_customers = 5000
num_merchants = 500
num_payment_methods = int(num_customers * 1.8)
num_payments = 100000

# 増分の期間とバッチ識別子
inc_start, inc_end = "2026-07-01", "2026-07-07"
batch_id = "20260707"

# 増分件数（初期より少なめ）
inc_payments = 10000
inc_points = 2000
inc_charges = 200
inc_logins = 2000

print(f"増分バッチ batch={batch_id}, 期間 {inc_start}〜{inc_end}, 決済{inc_payments:,}件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 共通の値定義

# COMMAND ----------

import dbldatagen as dg
from pyspark.sql import functions as F
from pyspark.sql.types import *

prefectures = ["東京都","神奈川県","大阪府","愛知県","埼玉県","千葉県","兵庫県","北海道","福岡県","静岡県",
               "京都府","広島県","宮城県","新潟県","長野県","岐阜県","群馬県","栃木県","岡山県","福島県"]
prefecture_weights = [14,9,9,7,7,6,5,5,5,4,3,3,2,2,2,2,2,2,2,2]
device_types = ["スマートフォン","PC","タブレット"]
device_type_weights = [70,20,10]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 増分①：決済履歴（t_payments）
# MAGIC 外部キー（customer_id / merchant_id / method_id）は既存マスターの範囲から採番。新しい日付で生成し、`batch=` サブディレクトリに出力する。

# COMMAND ----------

ds = (
    dg.DataGenerator(spark, name="inc_payments", rows=inc_payments, seedColumnName="_seed")
    # payment_id は初期(0..num_payments)と衝突しない採番オフセットを付与
    .withColumn("payment_id", StringType(), expr=f"format_string('PAY%012d', _seed + {num_payments})")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")  # 既存会員
    .withColumn("merchant_id", StringType(), expr=f"format_string('M%06d', cast(floor(rand()*{num_merchants}) as int))")   # 既存加盟店
    .withColumn("method_id", StringType(), expr=f"format_string('PM%08d', cast(floor(rand()*{num_payment_methods}) as int))")  # 既存決済手段
    .withColumn("payment_timestamp", TimestampType(), begin=inc_start+" 00:00:00", end=inc_end+" 23:59:59", random=True)  # ★7月の新しい日付
    .withColumn("amount", IntegerType(), minValue=100, maxValue=50000, random=True)
    .withColumn("status", StringType(), values=["完了","キャンセル","返金","エラー"], weights=[92,4,3,1], random=True)
    .withColumn("device_type", StringType(), values=device_types, weights=device_type_weights, random=True)
    .withColumn("device_id", StringType(), expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
    .withColumn("transaction_prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)
    .withColumn("ip_address_masked", StringType(),
                expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
    .withColumn("is_fraud", BooleanType(), values=[True,False], weights=[10,90], random=True)
)
df = ds.build().drop("_seed")
# ★既存ファイルを上書きせず、新規サブディレクトリ batch=... に出力
df.repartition(2).write.mode("overwrite").parquet(f"{shared_landing}/t_payments/batch={batch_id}/")
print(f"増分 t_payments: {df.count():,} 件 → batch={batch_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 増分②〜④：ポイント・チャージ・ログイン
# MAGIC いずれも customer_id は既存会員範囲、日付は7月で生成し、`batch=` サブディレクトリに出力する。

# COMMAND ----------

# --- ポイント ---
ds_pt = (
    dg.DataGenerator(spark, name="inc_points", rows=inc_points, seedColumnName="_seed")
    .withColumn("point_txn_id", StringType(), expr=f"format_string('PT%012d', _seed + 100000)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("payment_id", StringType(), expr=f"format_string('PAY%012d', cast(floor(rand()*{num_payments}) as int))")
    .withColumn("txn_type", StringType(), values=["付与","利用","失効"], weights=[70,25,5], random=True)
    .withColumn("points", IntegerType(), minValue=1, maxValue=500, random=True)
    .withColumn("txn_timestamp", TimestampType(), begin=inc_start+" 00:00:00", end=inc_end+" 23:59:59", random=True)
)
df_pt = ds_pt.build().drop("_seed")
df_pt = df_pt.withColumn("points", F.when(F.col("txn_type").isin("利用","失効"), -F.abs("points")).otherwise(F.abs("points")))
df_pt = df_pt.withColumn("payment_id", F.when(F.col("txn_type")=="失効", F.lit(None)).otherwise(F.col("payment_id")))
df_pt.repartition(1).write.mode("overwrite").parquet(f"{shared_landing}/t_point_transactions/batch={batch_id}/")
print(f"増分 t_point_transactions: {df_pt.count():,} 件")

# --- チャージ ---
ds_chg = (
    dg.DataGenerator(spark, name="inc_charges", rows=inc_charges, seedColumnName="_seed")
    .withColumn("charge_id", StringType(), expr=f"format_string('CHG%010d', _seed + 100000)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("amount", IntegerType(), values=[1000,2000,3000,5000,10000,20000,30000,50000], weights=[15,15,15,20,15,10,5,5], random=True)
    .withColumn("source", StringType(), values=["銀行口座","クレジットカード","ATM","ネットバンキング","オートチャージ"], weights=[30,25,15,10,20], random=True)
    .withColumn("charge_timestamp", TimestampType(), begin=inc_start+" 00:00:00", end=inc_end+" 23:59:59", random=True)
    .withColumn("status", StringType(), values=["成功","失敗"], weights=[97,3], random=True)
)
df_chg = ds_chg.build().drop("_seed")
df_chg.repartition(1).write.mode("overwrite").parquet(f"{shared_landing}/t_charges/batch={batch_id}/")
print(f"増分 t_charges: {df_chg.count():,} 件")

# --- ログイン ---
ds_lg = (
    dg.DataGenerator(spark, name="inc_logins", rows=inc_logins, seedColumnName="_seed")
    .withColumn("login_id", StringType(), expr=f"format_string('LGN%012d', _seed + 100000)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("login_timestamp", TimestampType(), begin=inc_start+" 00:00:00", end=inc_end+" 23:59:59", random=True)
    .withColumn("device_id", StringType(), expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
    .withColumn("device_type", StringType(), values=device_types, weights=device_type_weights, random=True)
    .withColumn("login_prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)
    .withColumn("ip_address_masked", StringType(),
                expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
    .withColumn("is_success", BooleanType(), values=[True,False], weights=[92,8], random=True)
    .withColumn("auth_method", StringType(), values=["パスワード","生体認証","SMS認証","パスキー"], weights=[40,30,20,10], random=True)
)
df_lg = ds_lg.build().drop("_seed")
df_lg.repartition(1).write.mode("overwrite").parquet(f"{shared_landing}/t_login_events/batch={batch_id}/")
print(f"増分 t_login_events: {df_lg.count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 投入結果の確認
# MAGIC 各ファクトのディレクトリに `batch=` サブディレクトリが増えたことを確認する。

# COMMAND ----------

for t in ["t_payments","t_point_transactions","t_charges","t_login_events"]:
    print(f"--- {t} ---")
    display(dbutils.fs.ls(f"{shared_landing}/{t}/"))
print("✅ 増分データ投入 完了")