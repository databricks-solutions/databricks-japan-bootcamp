# Databricks notebook source
# MAGIC %md
# MAGIC # 00. 初期データ生成（講師用）
# MAGIC
# MAGIC 架空の通信会社の決済サービスを模した不正検知用サンプルデータを生成する。
# MAGIC - **マスター3表**（会員・加盟店・決済手段）→ 共有 Volume に **Parquet** で出力
# MAGIC - **ファクト4表**（決済・ポイント・チャージ・ログイン）→ 共有 Volume に **Parquet** で出力
# MAGIC - 参加者全員に共有 Volume の **READ 権限**を付与し、各自の Bronze NB から直接読み取らせる
# MAGIC
# MAGIC > 実装作業用カタログ: `nabe_demo_us_west_2_catalog`（本番は `workshop`）

# COMMAND ----------

# MAGIC %md
# MAGIC ## ライブラリのインストール
# MAGIC 合成データ生成ライブラリ `dbldatagen` を導入する。

# COMMAND ----------

# MAGIC %pip install dbldatagen
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## パラメータ設定
# MAGIC カタログ・件数・期間を定義する。実装検証用に件数は縮小している。

# COMMAND ----------

# 保存先カタログ（実装作業用。本番は "workshop"）
catalog = "<ワークショップ用カタログ名>"
shared_schema = "de_workshop_shared"                       # 共有スキーマ

# レコード件数（実装検証用に縮小）
num_customers = 5000        # 会員数
num_merchants = 500         # 加盟店数
num_payment_methods = int(num_customers * 1.8)  # 決済手段（顧客あたり約1.8個）
num_payments = 100000       # 決済件数
num_point_transactions = 20000
num_charges = 2000
num_login_events = 20000

fraud_rate = 0.10           # 不正決済の割合（デモ用に10%）
date_start = "2026-01-01"   # 初期データ期間の開始
date_end = "2026-06-30"     # 初期データ期間の終了

print(f"catalog={catalog}, 会員={num_customers:,}, 決済={num_payments:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 共有スキーマ・Volume の作成と権限付与
# MAGIC 履歴データ(landing)とマスター(master)用の共有 Volume を作り、**参加者全員に READ 権限を付与**する。

# COMMAND ----------

import dbldatagen as dg
from pyspark.sql import functions as F
from pyspark.sql.types import *
import hashlib

# 共有スキーマと2つの共有 Volume を作成
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{shared_schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{shared_schema}.landing")   # ファクト Parquet 用
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{shared_schema}.master")    # マスター Parquet 用

shared_landing = f"/Volumes/{catalog}/{shared_schema}/landing"
shared_master  = f"/Volumes/{catalog}/{shared_schema}/master"

# ★重要：参加者全員に共有 Volume の READ 権限を事前付与（参加者は直接読み取る）
for vol in ["landing", "master"]:
    spark.sql(f"GRANT READ VOLUME ON VOLUME {catalog}.{shared_schema}.{vol} TO `account users`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {catalog}.{shared_schema} TO `account users`")

print("共有スキーマ・Volume 作成、READ 権限付与 完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 共通の値定義
# MAGIC 都道府県・通信プラン・デバイス種別など、各テーブルで共通利用する値を定義する。

# COMMAND ----------

# 都道府県（人口比の重み付き）
prefectures = ["東京都","神奈川県","大阪府","愛知県","埼玉県","千葉県","兵庫県","北海道","福岡県","静岡県",
               "京都府","広島県","宮城県","新潟県","長野県","岐阜県","群馬県","栃木県","岡山県","福島県"]
prefecture_weights = [14,9,9,7,7,6,5,5,5,4,3,3,2,2,2,2,2,2,2,2]

telecom_plans = ["5G無制限プラン","スタンダードプラン","ライト3GB","ライト6GB","ライト9GB","オンライン専用プラン"]
plan_weights = [15,20,20,15,10,20]
customer_statuses = ["アクティブ","休止","解約"]
status_weights = [85,10,5]
device_types = ["スマートフォン","PC","タブレット"]
device_type_weights = [70,20,10]

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスター生成①：会員（m_customers）
# MAGIC 会員属性に加え、不正検知の基準値（月間平均利用額・主利用デバイス）を持つ。生成後、共有 master Volume に **Parquet** で出力する。

# COMMAND ----------

ds_customers = (
    dg.DataGenerator(spark, name="m_customers", rows=num_customers, seedColumnName="_seed")
    .withColumn("customer_id", StringType(), expr="format_string('C%09d', _seed)")   # 顧客ID(PK)
    .withColumn("last_name", StringType(), values=["佐藤","鈴木","高橋","田中","伊藤","渡辺","山本","中村","小林","加藤"], random=True)
    .withColumn("first_name", StringType(), values=["太郎","次郎","健太","翔太","蓮","美咲","結衣","陽菜","美月","優子"], random=True)
    .withColumn("gender", StringType(), values=["M","F"], weights=[50,50], random=True)
    .withColumn("birth_date", DateType(), begin="1960-01-01", end="2005-12-31", random=True)
    .withColumn("prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)  # 登録住所
    .withColumn("registration_date", DateType(), begin="2019-01-01", end=date_start, random=True)
    .withColumn("telecom_plan", StringType(), values=telecom_plans, weights=plan_weights, random=True)
    .withColumn("customer_status", StringType(), values=customer_statuses, weights=status_weights, random=True)
    .withColumn("avg_monthly_spend", IntegerType(), minValue=5000, maxValue=80000, random=True)  # 月間平均利用額(不正判定の基準)
    .withColumn("primary_device_id", StringType(), expr="format_string('DEV%010d', _seed)")      # 主利用デバイス
)
df_customers = ds_customers.build().drop("_seed")
# ★共有 master Volume に Parquet 出力
df_customers.write.mode("overwrite").parquet(f"{shared_master}/m_customers/")
print(f"m_customers: {df_customers.count():,} 件 → {shared_master}/m_customers/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスター生成②：加盟店（m_merchants）
# MAGIC 業種カテゴリ・所在地を持つ。カテゴリは決済金額の妥当性に使う。

# COMMAND ----------

merchant_categories = ["コンビニ","スーパー","飲食","ドラッグストア","ECサイト","家電量販","アパレル","交通","エンタメ"]
category_weights = [20,15,20,10,15,5,5,5,5]

ds_merchants = (
    dg.DataGenerator(spark, name="m_merchants", rows=num_merchants, seedColumnName="_seed")
    .withColumn("merchant_id", StringType(), expr="format_string('M%06d', _seed)")   # 加盟店ID(PK)
    .withColumn("category", StringType(), values=merchant_categories, weights=category_weights, random=True)
    .withColumn("prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)
)
df_merchants = ds_merchants.build().drop("_seed")
# 加盟店名をカテゴリ + 支店番号で付与
df_merchants = df_merchants.withColumn(
    "merchant_name",
    F.concat(F.col("category"), F.lit("店"),
             (F.abs(F.hash(F.col("merchant_id"))) % 300 + 1).cast("string"), F.lit("号"))
)
df_merchants.write.mode("overwrite").parquet(f"{shared_master}/m_merchants/")
print(f"m_merchants: {df_merchants.count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスター生成③：決済手段（m_payment_methods）
# MAGIC 顧客が保有する決済手段（QR/クレカ/iD/デビット）。customer_id は既存会員の範囲から採番する。

# COMMAND ----------

method_types = ["QR決済","クレジットカード","iD","デビットカード"]
method_weights = [35,30,20,15]

ds_pm = (
    dg.DataGenerator(spark, name="m_payment_methods", rows=num_payment_methods, seedColumnName="_seed")
    .withColumn("method_id", StringType(), expr="format_string('PM%08d', _seed)")   # 決済手段ID(PK)
    # customer_id は 0..num_customers-1 の範囲で採番 → 既存会員に必ず紐づく
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand() * {num_customers}) as int))")
    .withColumn("method_type", StringType(), values=method_types, weights=method_weights, random=True)
    .withColumn("card_number_masked", StringType(),
                expr="concat('****-****-****-', format_string('%04d', cast(floor(rand()*10000) as int)))")
    .withColumn("registered_date", DateType(), begin="2019-01-01", end=date_start, random=True)
    .withColumn("status", StringType(), values=["有効","停止","期限切れ"], weights=[90,5,5], random=True)
)
df_pm = ds_pm.build().drop("_seed")
df_pm.write.mode("overwrite").parquet(f"{shared_master}/m_payment_methods/")
print(f"m_payment_methods: {df_pm.count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ファクト生成①：決済履歴（t_payments）
# MAGIC 主テーブル。不正ラベル(`is_fraud`)と5つの不正パターン（深夜大量/地理異常/高額/カードテスト/乗っ取り）を注入する。

# COMMAND ----------

payment_statuses = ["完了","キャンセル","返金","エラー"]
payment_status_weights = [92,4,3,1]

# Step1: 基本データ生成（各外部キーは既存マスターの範囲から採番）
ds_pay = (
    dg.DataGenerator(spark, name="t_payments", rows=num_payments, seedColumnName="_seed")
    .withColumn("payment_id", StringType(), expr="format_string('PAY%012d', _seed)")   # 決済ID(PK)
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("merchant_id", StringType(), expr=f"format_string('M%06d', cast(floor(rand()*{num_merchants}) as int))")
    .withColumn("method_id", StringType(), expr=f"format_string('PM%08d', cast(floor(rand()*{num_payment_methods}) as int))")
    .withColumn("payment_timestamp", TimestampType(), begin=date_start+" 00:00:00", end=date_end+" 23:59:59", random=True)
    .withColumn("amount", IntegerType(), minValue=100, maxValue=50000, random=True)
    .withColumn("status", StringType(), values=payment_statuses, weights=payment_status_weights, random=True)
    .withColumn("device_type", StringType(), values=device_types, weights=device_type_weights, random=True)
    .withColumn("device_id", StringType(), expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
    .withColumn("transaction_prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)
    .withColumn("ip_address_masked", StringType(),
                expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
)
df_pay = ds_pay.build().drop("_seed")

# Step2: 不正フラグとパターンの割り当て
df_pay = df_pay.withColumn("is_fraud", (F.rand() < fraud_rate))
df_pay = df_pay.withColumn("_pat",
    F.when(~F.col("is_fraud"), F.lit("normal"))
     .when(F.rand() < 0.30, F.lit("深夜大量"))
     .when(F.rand() < 0.36, F.lit("地理異常"))
     .when(F.rand() < 0.44, F.lit("高額異常"))
     .when(F.rand() < 0.60, F.lit("カードテスト"))
     .otherwise(F.lit("乗っ取り")))

# 会員属性を結合（不正パターンの特徴調整に使用）
df_pay = df_pay.join(
    df_customers.select("customer_id", F.col("prefecture").alias("home_pref"),
                        "avg_monthly_spend", "primary_device_id"),
    on="customer_id", how="left")

# 「深夜大量」: 時刻を2〜5時台へ
df_pay = df_pay.withColumn("payment_timestamp",
    F.when(F.col("_pat")=="深夜大量",
           F.col("payment_timestamp").cast("date").cast("timestamp")
           + F.expr("make_interval(0,0,0,0,cast(floor(rand()*3+2) as int),cast(floor(rand()*60) as int),0)"))
     .otherwise(F.col("payment_timestamp")))

# 「地理異常」: 遠隔地に変更 / 正常は8割が自宅と一致
_remote = ["北海道","青森県","沖縄県","鹿児島県","岩手県","秋田県","山形県","宮崎県"]
df_pay = df_pay.withColumn("transaction_prefecture",
    F.when(F.col("_pat")=="地理異常",
           F.array(*[F.lit(p) for p in _remote]).getItem((F.abs(F.hash("payment_id")) % len(_remote))))
     .when(~F.col("is_fraud"), F.when(F.rand()<0.8, F.col("home_pref")).otherwise(F.col("transaction_prefecture")))
     .otherwise(F.col("transaction_prefecture")))

# 「高額異常」: 通常の5〜10倍
df_pay = df_pay.withColumn("amount",
    F.when(F.col("_pat")=="高額異常",
           F.least((F.col("avg_monthly_spend")*(F.rand()*5+5)/30).cast("int"), F.lit(500000)))
     .otherwise(F.col("amount")))

# 「カードテスト」: 少額(100〜500)
df_pay = df_pay.withColumn("amount",
    F.when(F.col("_pat")=="カードテスト", (F.rand()*400+100).cast("int")).otherwise(F.col("amount")))

# 「乗っ取り」: 新規デバイス / 正常は9割が主デバイス
df_pay = df_pay.withColumn("device_id",
    F.when(F.col("_pat")=="乗っ取り", F.concat(F.lit("DEV_NEW_"), F.substring(F.md5("payment_id"),1,8)))
     .when((~F.col("is_fraud")) & (F.rand()<0.9), F.col("primary_device_id"))
     .otherwise(F.col("device_id")))

df_pay = df_pay.drop("_pat","home_pref","avg_monthly_spend","primary_device_id")
# ★共有 landing Volume に Parquet 出力（8ファイルに分割 → 増分取り込み体験のため）
df_pay.repartition(8).write.mode("overwrite").parquet(f"{shared_landing}/t_payments/")
print(f"t_payments: {df_pay.count():,} 件 → {shared_landing}/t_payments/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ファクト生成②〜④：ポイント・チャージ・ログイン
# MAGIC いずれも customer_id は既存会員の範囲から採番し、共有 landing Volume に Parquet 出力する。

# COMMAND ----------

# --- ポイント取引 ---
ds_pt = (
    dg.DataGenerator(spark, name="t_point_transactions", rows=num_point_transactions, seedColumnName="_seed")
    .withColumn("point_txn_id", StringType(), expr="format_string('PT%012d', _seed)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("payment_id", StringType(), expr=f"format_string('PAY%012d', cast(floor(rand()*{num_payments}) as int))")
    .withColumn("txn_type", StringType(), values=["付与","利用","失効"], weights=[70,25,5], random=True)
    .withColumn("points", IntegerType(), minValue=1, maxValue=500, random=True)
    .withColumn("txn_timestamp", TimestampType(), begin=date_start+" 00:00:00", end=date_end+" 23:59:59", random=True)
)
df_pt = ds_pt.build().drop("_seed")
df_pt = df_pt.withColumn("points", F.when(F.col("txn_type").isin("利用","失効"), -F.abs("points")).otherwise(F.abs("points")))
df_pt = df_pt.withColumn("payment_id", F.when(F.col("txn_type")=="失効", F.lit(None)).otherwise(F.col("payment_id")))
df_pt.repartition(4).write.mode("overwrite").parquet(f"{shared_landing}/t_point_transactions/")
print(f"t_point_transactions: {df_pt.count():,} 件")

# --- チャージ履歴 ---
ds_chg = (
    dg.DataGenerator(spark, name="t_charges", rows=num_charges, seedColumnName="_seed")
    .withColumn("charge_id", StringType(), expr="format_string('CHG%010d', _seed)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("amount", IntegerType(), values=[1000,2000,3000,5000,10000,20000,30000,50000], weights=[15,15,15,20,15,10,5,5], random=True)
    .withColumn("source", StringType(), values=["銀行口座","クレジットカード","ATM","ネットバンキング","オートチャージ"], weights=[30,25,15,10,20], random=True)
    .withColumn("charge_timestamp", TimestampType(), begin=date_start+" 00:00:00", end=date_end+" 23:59:59", random=True)
    .withColumn("status", StringType(), values=["成功","失敗"], weights=[97,3], random=True)
)
df_chg = ds_chg.build().drop("_seed")
df_chg.repartition(2).write.mode("overwrite").parquet(f"{shared_landing}/t_charges/")
print(f"t_charges: {df_chg.count():,} 件")

# --- ログイン履歴 ---
ds_lg = (
    dg.DataGenerator(spark, name="t_login_events", rows=num_login_events, seedColumnName="_seed")
    .withColumn("login_id", StringType(), expr="format_string('LGN%012d', _seed)")
    .withColumn("customer_id", StringType(), expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
    .withColumn("login_timestamp", TimestampType(), begin=date_start+" 00:00:00", end=date_end+" 23:59:59", random=True)
    .withColumn("device_id", StringType(), expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
    .withColumn("device_type", StringType(), values=device_types, weights=device_type_weights, random=True)
    .withColumn("login_prefecture", StringType(), values=prefectures, weights=prefecture_weights, random=True)
    .withColumn("ip_address_masked", StringType(),
                expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
    .withColumn("is_success", BooleanType(), values=[True,False], weights=[92,8], random=True)
    .withColumn("auth_method", StringType(), values=["パスワード","生体認証","SMS認証","パスキー"], weights=[40,30,20,10], random=True)
)
df_lg = ds_lg.build().drop("_seed")
df_lg.repartition(4).write.mode("overwrite").parquet(f"{shared_landing}/t_login_events/")
print(f"t_login_events: {df_lg.count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 生成結果の確認
# MAGIC 共有 Volume に出力された Parquet の一覧と、決済の不正率を確認する。

# COMMAND ----------

print("=== master Volume ===")
display(dbutils.fs.ls(f"{shared_master}"))
print("=== landing Volume ===")
display(dbutils.fs.ls(f"{shared_landing}"))

fraud = df_pay.filter(F.col("is_fraud")).count()
total = df_pay.count()
print(f"不正率: {fraud:,}/{total:,} = {fraud/total*100:.1f}%")
print("✅ 初期データ生成 完了")