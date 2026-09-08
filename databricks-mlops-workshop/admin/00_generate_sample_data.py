# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# dependencies = [
#   "dbldatagen",
# ]
# ///
# MAGIC %md
# MAGIC # サンプルデータ生成（不正決済検知ワークショップ用・全テーブル一括生成）
# MAGIC
# MAGIC このノートブック **1本で、ワークショップに必要なソーステーブルをすべて** 生成します。
# MAGIC
# MAGIC | 区分 | テーブル | 生成方法 |
# MAGIC |---|---|---|
# MAGIC | マスタ | `m_customers` / `m_merchants` / `m_payment_methods` | `dbldatagen` で合成生成 |
# MAGIC | トランザクション | `t_payments` / `t_login_events` | **特徴量に依存した確率的ロジック**で生成（下記） |
# MAGIC | トランザクション | `t_charges` | `dbldatagen` で合成生成 |
# MAGIC
# MAGIC ## `t_payments` / `t_login_events` の設計（ワークショップの学習効果を出すための工夫）
# MAGIC 1. **タイムスタンプに実時刻（時分秒）を付与** — 時系列特徴量が日次集計なしで素直に作れ、Point-in-Time 結合が厳密になる。
# MAGIC 2. **`is_fraud` を「教える特徴量」に依存させて確率的に生成** — 以下の要因を混合し、ロジスティック＋ノイズで生成:
# MAGIC    - デバイス不一致（取引の `device_id` ≠ 顧客の `primary_device_id`）
# MAGIC    - 地域不一致（取引の `transaction_prefecture` ≠ 顧客の居住県）
# MAGIC    - 加盟店固有のリスク（加盟店ごとの潜在リスク）
# MAGIC    - 金額 ÷ 顧客の平均利用額（高額比率）
# MAGIC    - **取引直前24hの失敗ログイン数**（→ Point-in-Time 時系列特徴量に意味を与える）
# MAGIC 3. **決定論を避け、確率的（base_rate 約2〜3%＋ノイズ）** — 単一特徴で完璧分離にならないよう調整。
# MAGIC
# MAGIC > 実行すると対象スキーマの各テーブルを上書きします。データ生成には `dbldatagen`（Serverless 対応）を使用します。

# COMMAND ----------

# dbldatagen を導入（環境ヘッダーの dependencies でも指定済み。Serverless での確実な導入のため明示）
%pip install -q dbldatagen
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## パラメータ設定
# MAGIC 保存先カタログ・スキーマと件数・期間を指定します（開催時は `CATALOG` を書き換えてください）。

# COMMAND ----------

# ===== この変数の値(カタログ名)だけ書き換えてください =====
CATALOG = "<ワークショップ用カタログ名>"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 以下のセルは変更不要

# COMMAND ----------

SCHEMA  = "mlops_ws_shared"
SRC = f"{CATALOG}.{SCHEMA}"

# dbldatagen ベースのマスタ生成セルが参照するエイリアス
catalog_name = CATALOG
schema_name  = SCHEMA

# レコード件数（マスタ・チャージ）
num_customers       = 50000
num_merchants       = 5000
num_payment_methods = int(num_customers * 1.8)   # 顧客あたり平均約1.8個
num_charges         = 20000

# データ期間
date_start = "2026-01-01"
date_end   = "2026-06-30"

print(f"保存先: {SRC}")
print(f"データ期間: {date_start} ～ {date_end}")
print(f"件数: 顧客={num_customers:,}, 加盟店={num_merchants:,}, 決済手段={num_payment_methods:,}, チャージ={num_charges:,}")

# COMMAND ----------

# DBTITLE 1,ライブラリのインポートと初期設定
import dbldatagen as dg
from pyspark.sql import functions as F, Window
from pyspark.sql.types import *
from datetime import datetime

# スキーマ作成
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SRC}")

# COMMAND ----------

# MAGIC %md
# MAGIC # マスターテーブルの生成（`dbldatagen`）

# COMMAND ----------

# DBTITLE 1,マスターテーブル: m_customers（会員情報）
# =============================================================
# m_customers: 会員情報マスター
# =============================================================

# 都道府県リスト（人口比率に応じた重み付け）
prefectures = [
    "東京都", "神奈川県", "大阪府", "愛知県", "埼玉県",
    "千葉県", "兵庫県", "北海道", "福岡県", "静岡県",
    "京都府", "広島県", "宮城県", "新潟県", "長野県",
    "岐阜県", "群馬県", "栃木県", "岡山県", "福島県"
]
prefecture_weights = [14, 9, 9, 7, 7, 6, 5, 5, 5, 4, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2]

# 通信プラン
telecom_plans = ["5G無制限プラン", "スタンダードプラン", "ライト3GB", "ライト6GB", "ライト9GB", "オンライン専用プラン"]
plan_weights = [15, 20, 20, 15, 10, 20]

# 会員ステータス
customer_statuses = ["アクティブ", "休止", "解約"]
status_weights = [85, 10, 5]

# デバイスリスト（全テーブルで共通利用）
device_types = ["スマートフォン", "PC", "タブレット"]
device_type_weights = [70, 20, 10]

ds_customers = (
    dg.DataGenerator(spark, name="m_customers", rows=num_customers, seedColumnName="_seed")
    .withColumn("customer_id", StringType(), expr="format_string('C%09d', _seed)")
    .withColumn("last_name", StringType(),
                values=["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
                        "吉田", "山田", "佐々木", "松本", "井上", "木村", "林", "清水", "山口", "森"],
                random=True)
    .withColumn("first_name", StringType(),
                values=["太郎", "次郎", "健太", "翔太", "蓮", "湊斗", "悠真",
                        "美咲", "結衣", "さくら", "陽菜", "美月", "優子", "真由"],
                random=True)
    .withColumn("gender", StringType(), values=["M", "F"], weights=[50, 50], random=True)
    .withColumn("birth_date", DateType(),
                begin="1960-01-01", end="2005-12-31", random=True)
    .withColumn("prefecture", StringType(),
                values=prefectures, weights=prefecture_weights, random=True)
    .withColumn("registration_date", DateType(),
                begin="2019-01-01", end=date_start, random=True)
    .withColumn("telecom_plan", StringType(),
                values=telecom_plans, weights=plan_weights, random=True)
    .withColumn("customer_status", StringType(),
                values=customer_statuses, weights=status_weights, random=True)
    .withColumn("avg_monthly_spend", IntegerType(),
                minValue=5000, maxValue=80000, random=True)
    .withColumn("primary_device_id", StringType(),
                expr="format_string('DEV%010d', _seed)")
)

df_customers = ds_customers.build().drop("_seed")
df_customers.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.m_customers")
print(f"m_customers: {df_customers.count():,} 件書き込み完了")
df_customers.show(5, truncate=False)

# COMMAND ----------

# DBTITLE 1,マスターテーブル: m_merchants（加盟店情報）
# =============================================================
# m_merchants: 加盟店情報マスター
# =============================================================

# 加盟店カテゴリと重み
merchant_categories = ["コンビニ", "スーパー", "飲食", "ドラッグストア", "ECサイト", "家電量販", "アパレル", "交通", "エンタメ"]
category_weights = [20, 15, 20, 10, 15, 5, 5, 5, 5]

# カテゴリ別店舗名プレフィックス（架空のブランド名）
merchant_prefixes = {
    "コンビニ": ["コンビニA", "コンビニB", "コンビニC", "コンビニD", "コンビニE"],
    "スーパー": ["スーパーA", "スーパーB", "スーパーC", "スーパーD", "スーパーE"],
    "飲食": ["レストランA", "カフェB", "ファストフードC", "居酒屋D", "ファミレE"],
    "ドラッグストア": ["ドラッグストアA", "ドラッグストアB", "ドラッグストアC", "ドラッグストアD", "ドラッグストアE"],
    "ECサイト": ["ECモールA", "ECマーケットB", "ECショップC", "フラションD", "フリマE"],
    "家電量販": ["家電A", "家電B", "家電C", "家電D", "家電E"],
    "アパレル": ["アパレルA", "アパレルB", "アパレルC", "アパレルD", "アパレルE"],
    "交通": ["鉄道A", "鉄道B", "地下鉄C", "私鉄D", "私鉄E"],
    "エンタメ": ["映画館A", "動画B", "音楽C", "ゲームD", "エンタE"]
}

ds_merchants = (
    dg.DataGenerator(spark, name="m_merchants", rows=num_merchants, seedColumnName="_seed")
    .withColumn("merchant_id", StringType(), expr="format_string('M%06d', _seed)")
    .withColumn("category", StringType(),
                values=merchant_categories, weights=category_weights, random=True)
    .withColumn("prefecture", StringType(),
                values=prefectures, weights=prefecture_weights, random=True)
)

df_merchants = ds_merchants.build().drop("_seed")

# カテゴリに応じた店舗名をUDFで付与
import hashlib

@F.udf(StringType())
def generate_merchant_name(merchant_id, category):
    prefixes = merchant_prefixes.get(category, ["店舗"])
    idx = int(hashlib.md5(merchant_id.encode()).hexdigest(), 16) % len(prefixes)
    branch_num = int(hashlib.md5((merchant_id + "branch").encode()).hexdigest(), 16) % 300 + 1
    return f"{prefixes[idx]} {category}店{branch_num}号"

df_merchants = df_merchants.withColumn(
    "merchant_name", generate_merchant_name(F.col("merchant_id"), F.col("category"))
)

df_merchants.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.m_merchants")
print(f"m_merchants: {df_merchants.count():,} 件書き込み完了")
df_merchants.show(5, truncate=False)

# COMMAND ----------

# DBTITLE 1,マスターテーブル: m_payment_methods（決済手段）
# =============================================================
# m_payment_methods: 決済手段マスター
# 顧客1人あたり1～3つの決済手段を保有
# =============================================================

method_types = ["QR決済", "クレジットカード", "iD", "デビットカード"]
method_weights = [35, 30, 20, 15]
method_statuses = ["有効", "停止", "期限切れ"]
method_status_weights = [90, 5, 5]

ds_payment_methods = (
    dg.DataGenerator(spark, name="m_payment_methods", rows=num_payment_methods, seedColumnName="_seed")
    .withColumn("method_id", StringType(), expr="format_string('PM%08d', _seed)")
    .withColumn("customer_id", StringType(),
                expr=f"format_string('C%09d', cast(floor(rand() * {num_customers}) as int))")
    .withColumn("method_type", StringType(),
                values=method_types, weights=method_weights, random=True)
    .withColumn("card_number_masked", StringType(),
                expr="concat('****-****-****-', format_string('%04d', cast(floor(rand() * 10000) as int)))")
    .withColumn("registered_date", DateType(),
                begin="2019-01-01", end=date_start, random=True)
    .withColumn("status", StringType(),
                values=method_statuses, weights=method_status_weights, random=True)
)

df_payment_methods = ds_payment_methods.build().drop("_seed")
df_payment_methods.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.m_payment_methods")
print(f"m_payment_methods: {df_payment_methods.count():,} 件書き込み完了")
df_payment_methods.show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC # トランザクション生成（`t_payments` / `t_login_events`）
# MAGIC ここからは、**マスタを参照しつつ「教える特徴量」に依存した確率的ロジック**で決済とログインを生成します。
# MAGIC （不正率 約2〜3%。デバイス/地域不一致・加盟店リスク・高額比率・直前24h失敗ログインが `is_fraud` に効くよう設計）

# COMMAND ----------

# トランザクション生成のパラメータ
N_ACTIVE        = num_customers   # アクティブ顧客数（C000000000..）
PAY_PER_CUST    = 20              # 顧客あたり決済件数（→ 約100万件）
LOGIN_PER_CUST  = 18              # 顧客あたり通常ログイン件数
MERCH_POOL      = num_merchants   # 使用する加盟店プール（M000000..）
START_TS        = date_start + " 00:00:00"
PERIOD_DAYS     = 181             # 2026-06-30 まで
INJECT_FRAC     = 0.15            # 取引前に失敗ログインを注入する割合
FRAUD_INTERCEPT = -7.5            # base_rate 調整用（小さいほど不正率が下がる）。全体不正率 ~2-3% を狙う

# 決済/ログインの都道府県プール（マスタと同じ20県。順序は問わない）
PREFS = ['東京都','大阪府','神奈川県','埼玉県','愛知県','千葉県','北海道','兵庫県','福岡県','静岡県',
         '広島県','京都府','岡山県','長野県','新潟県','群馬県','栃木県','宮城県','岐阜県','福島県']
prefs_col = F.array([F.lit(p) for p in PREFS])

TMP_PAY   = f"{SRC}._tmp_pay_raw"
TMP_LOGIN = f"{SRC}._tmp_login_raw"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. アクティブ顧客と潜在リスクを準備
# MAGIC 顧客ごとに潜在リスク `r_c`（ハッシュ由来の 0〜1）を付与。デバイス変更や失敗ログインの起きやすさに反映します。

# COMMAND ----------

cust = (spark.table(f"{SRC}.m_customers")
        .withColumn("cust_num", F.expr("CAST(substr(customer_id,2) AS INT)"))
        .where(F.col("cust_num") < N_ACTIVE)
        .select("customer_id", "cust_num",
                F.col("prefecture").alias("cust_pref"),
                "primary_device_id",
                F.coalesce(F.col("avg_monthly_spend"), F.lit(30000)).alias("avg_monthly_spend"))
        .withColumn("r_c", F.pmod(F.hash("customer_id"), F.lit(1000)) / 1000.0))

# 顧客ごとの代表 method_id（参照整合のため。特徴量には未使用）
method_by_cust = (spark.table(f"{SRC}.m_payment_methods")
                  .groupBy("customer_id").agg(F.first("method_id").alias("method_id")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 決済の「生の乱数」を生成して一時テーブルに materialize
# MAGIC `rand()` は非決定的なため、先に一時テーブルへ固定してから決定論的に属性を派生させます。

# COMMAND ----------

start_sec = F.unix_timestamp(F.lit(START_TS))
pay_raw = (cust.crossJoin(spark.range(PAY_PER_CUST).withColumnRenamed("id", "k"))
    .withColumn("ts_sec",     start_sec + (F.rand() * PERIOD_DAYS * 86400).cast("long"))
    .withColumn("merchant_idx", (F.rand() * MERCH_POOL).cast("int"))
    .withColumn("u_dev",   F.rand())
    .withColumn("u_geo",   F.rand())
    .withColumn("u_pref",  F.rand())
    .withColumn("u_amt",   F.rand())
    .withColumn("u_large", F.rand())
    .withColumn("u_dt",    F.rand())
    .withColumn("u_status",F.rand())
    .withColumn("u_ip",    F.rand())
    .withColumn("u_inj",   F.rand()))
pay_raw.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TMP_PAY)
print("tmp payments rows:", spark.table(TMP_PAY).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 決済属性を決定論的に派生（固定済み乱数から）

# COMMAND ----------

p = spark.table(TMP_PAY)
p = (p
    .withColumn("payment_timestamp", F.to_timestamp(F.col("ts_sec")))
    .withColumn("payment_uid", F.concat_ws("_", F.col("customer_id"), F.col("k")))
    .withColumn("payment_id", F.format_string("PAY%08d%02d", F.col("cust_num"), F.col("k")))
    .withColumn("merchant_id", F.format_string("M%06d", F.col("merchant_idx")))
    .withColumn("merchant_risk", F.pmod(F.hash(F.col("merchant_id")), F.lit(1000)) / 1000.0)
    # デバイス不一致（リスク顧客ほど起きやすい）
    .withColumn("dev_mismatch_gen", (F.col("u_dev") < (0.05 + 0.5 * F.col("r_c"))))
    .withColumn("device_id", F.when(F.col("dev_mismatch_gen"),
                    F.concat(F.lit("DEV"), F.lpad((F.col("u_dev") * 1e10).cast("long").cast("string"), 10, "0")))
                 .otherwise(F.col("primary_device_id")))
    # 地域不一致
    .withColumn("gen_pref", prefs_col[(F.col("u_pref") * 20).cast("int")])
    .withColumn("transaction_prefecture", F.when(F.col("u_geo") < (0.05 + 0.4 * F.col("r_c")),
                    F.col("gen_pref")).otherwise(F.col("cust_pref")))
    # 金額（平均利用額の 2〜22%。まれに高額）
    .withColumn("amount", F.greatest(F.lit(100),
                    (F.col("avg_monthly_spend") * (0.02 + F.col("u_amt") * 0.2)
                     * F.when(F.col("u_large") < 0.05, F.lit(5)).otherwise(F.lit(1))).cast("int")))
    .withColumn("device_type", F.when(F.col("u_dt") < 0.7, "スマートフォン")
                    .when(F.col("u_dt") < 0.9, "PC").otherwise("タブレット"))
    .withColumn("status", F.when(F.col("u_status") < 0.92, "完了")
                    .when(F.col("u_status") < 0.95, "キャンセル")
                    .when(F.col("u_status") < 0.98, "エラー").otherwise("返金"))
    .withColumn("ip_address_masked",
                    F.concat_ws(".", (F.col("u_ip") * 255).cast("int").cast("string"),
                                (F.col("u_amt") * 255).cast("int").cast("string"),
                                (F.col("u_dt") * 255).cast("int").cast("string"), F.lit("***")))
    .withColumn("inject_fail", F.col("u_inj") < INJECT_FRAC))
p = p.join(method_by_cust, "customer_id", "left") \
     .withColumn("method_id", F.coalesce(F.col("method_id"), F.format_string("PM%08d", F.col("cust_num"))))
print("payments prepared:", p.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. ログイン生成（通常ログイン ＋ 取引直前の失敗ログイン注入）
# MAGIC 一部の決済の直前（1〜24h前）に失敗ログインを注入し、時系列特徴量に学習可能なシグナルを持たせます。

# COMMAND ----------

# 通常ログイン（生の乱数 → 一時テーブル）
login_raw = (cust.crossJoin(spark.range(LOGIN_PER_CUST).withColumnRenamed("id", "k"))
    .withColumn("ts_sec", start_sec + (F.rand() * PERIOD_DAYS * 86400).cast("long"))
    .withColumn("u_succ", F.rand()).withColumn("u_auth", F.rand())
    .withColumn("u_dt", F.rand()).withColumn("u_geo", F.rand()).withColumn("u_pref", F.rand())
    .withColumn("u_ip", F.rand()))
login_raw.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TMP_LOGIN)

auth_arr = F.array(F.lit("パスワード"), F.lit("SMS認証"), F.lit("生体認証"), F.lit("パスキー"))
lr = spark.table(TMP_LOGIN)
benign = (lr
    .withColumn("login_timestamp", F.to_timestamp(F.col("ts_sec")))
    .withColumn("is_success", F.col("u_succ") > 0.10)
    .withColumn("device_id", F.col("primary_device_id"))
    .withColumn("device_type", F.when(F.col("u_dt") < 0.7, "スマートフォン").when(F.col("u_dt") < 0.9, "PC").otherwise("タブレット"))
    .withColumn("login_prefecture", F.when(F.col("u_geo") < 0.9, F.col("cust_pref")).otherwise(prefs_col[(F.col("u_pref") * 20).cast("int")]))
    .withColumn("auth_method", auth_arr[(F.col("u_auth") * 4).cast("int")])
    .withColumn("ip_address_masked", F.concat_ws(".", (F.col("u_ip") * 255).cast("int").cast("string"), F.lit("0"), F.lit("0"), F.lit("***")))
    .select("customer_id", "login_timestamp", "device_id", "device_type", "login_prefecture", "is_success", "auth_method", "ip_address_masked"))

# 注入する失敗ログイン（該当決済ごとに2件、取引の1〜24h前）
inj = (p.where(F.col("inject_fail"))
    .crossJoin(spark.range(2).withColumnRenamed("id", "j"))
    .withColumn("login_timestamp", F.to_timestamp(F.col("ts_sec") - (F.lit(3600) + (F.rand() * 23 * 3600)).cast("long")))
    .withColumn("device_id", F.concat(F.lit("DEV"), F.lpad((F.rand() * 1e10).cast("long").cast("string"), 10, "0")))
    .withColumn("device_type", F.lit("PC"))
    .withColumn("login_prefecture", prefs_col[(F.rand() * 20).cast("int")])
    .withColumn("is_success", F.lit(False))
    .withColumn("auth_method", F.lit("パスワード"))
    .withColumn("ip_address_masked", F.lit("203.0.113.***"))
    .select("customer_id", "login_timestamp", "device_id", "device_type", "login_prefecture", "is_success", "auth_method", "ip_address_masked"))

logins = (benign.unionByName(inj)
          .dropDuplicates(["customer_id", "login_timestamp"])
          .withColumn("login_id", F.concat(F.lit("LGN"), F.lpad(F.monotonically_increasing_id().cast("string"), 12, "0"))))
logins.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.t_login_events")
print("t_login_events rows:", spark.table(f"{SRC}.t_login_events").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 取引直前24hの失敗ログイン数を計算（Point-in-Time 相当）

# COMMAND ----------

l = spark.table(f"{SRC}.t_login_events").withColumn("ts_sec", F.unix_timestamp("login_timestamp"))
ev = (p.select("customer_id", F.col("ts_sec").alias("ts_sec"), F.lit(0).alias("fail_ind"),
               F.lit(1).alias("is_pay"), "payment_uid")
      .unionByName(
        l.select("customer_id", "ts_sec", (~F.col("is_success")).cast("int").alias("fail_ind"),
                 F.lit(0).alias("is_pay"), F.lit(None).cast("string").alias("payment_uid"))))
w24 = Window.partitionBy("customer_id").orderBy("ts_sec").rangeBetween(-86400, 0)
rf = (ev.withColumn("recent_fail", F.sum("fail_ind").over(w24))
        .where(F.col("is_pay") == 1)
        .select("payment_uid", "recent_fail"))
p2 = p.join(rf, "payment_uid", "left").withColumn("recent_fail", F.coalesce(F.col("recent_fail"), F.lit(0)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. is_fraud を確率的に生成（ロジスティック＋ノイズ）

# COMMAND ----------

z = (F.lit(FRAUD_INTERCEPT)
     + 3.0 * (F.col("device_id") != F.col("primary_device_id")).cast("double")
     + 2.2 * (F.col("transaction_prefecture") != F.col("cust_pref")).cast("double")
     + 3.5 * (F.col("merchant_risk") - 0.5)
     + 1.0 * F.least(F.col("amount") / (F.col("avg_monthly_spend") + 1000), F.lit(5.0))
     + 1.5 * F.least(F.col("recent_fail").cast("double"), F.lit(3.0))
     + F.randn() * 0.7)
p3 = (p2.withColumn("prob", 1.0 / (1.0 + F.exp(-z)))
        .withColumn("is_fraud", F.rand() < F.col("prob")))

t_payments = p3.select(
    "customer_id", "merchant_id", "payment_id", "method_id", "payment_timestamp",
    "amount", "status", "device_type", "device_id", "transaction_prefecture",
    "ip_address_masked", "is_fraud")
t_payments.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.t_payments")
print("t_payments rows:", spark.table(f"{SRC}.t_payments").count())

# 一時テーブルを削除
spark.sql(f"DROP TABLE IF EXISTS {TMP_PAY}")
spark.sql(f"DROP TABLE IF EXISTS {TMP_LOGIN}")

# COMMAND ----------

# DBTITLE 1,トランザクションテーブル: t_charges（チャージ履歴）
# =============================================================
# t_charges: チャージ（残高入金）トランザクション
# =============================================================

charge_sources = ["銀行口座", "クレジットカード", "ATM", "ネットバンキング", "オートチャージ"]
charge_source_weights = [30, 25, 15, 10, 20]

# チャージ金額は切りの良い数字が多い
charge_amounts = [1000, 2000, 3000, 5000, 10000, 20000, 30000, 50000]
charge_amount_weights = [15, 15, 15, 20, 15, 10, 5, 5]

ds_charges = (
    dg.DataGenerator(spark, name="t_charges", rows=num_charges, seedColumnName="_seed")
    .withColumn("charge_id", StringType(), expr="format_string('CHG%010d', _seed)")
    .withColumn("customer_id", StringType(),
                expr=f"format_string('C%09d', cast(floor(rand() * {num_customers}) as int))")
    .withColumn("amount", IntegerType(),
                values=charge_amounts, weights=charge_amount_weights, random=True)
    .withColumn("source", StringType(),
                values=charge_sources, weights=charge_source_weights, random=True)
    .withColumn("charge_timestamp", TimestampType(),
                begin=date_start + " 00:00:00", end=date_end + " 23:59:59", random=True)
    .withColumn("status", StringType(),
                values=["成功", "失敗"], weights=[97, 3], random=True)
)

df_charges = ds_charges.build().drop("_seed")
df_charges.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SRC}.t_charges")
print(f"t_charges: {df_charges.count():,} 件書き込み完了")
df_charges.show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 生成結果の検証（件数サマリー＋不正率と各シグナルの効き）

# COMMAND ----------

# 各テーブルの件数サマリー
print("=" * 50)
print("生成テーブル 件数サマリー")
print("=" * 50)
for t in ["m_customers", "m_merchants", "m_payment_methods", "t_payments", "t_login_events", "t_charges"]:
    print(f"  {t:20s}: {spark.table(f'{SRC}.{t}').count():,} 件")

# 不正率と各シグナルの効き（特徴量が予測に効いていることの確認）
display(spark.sql(f"""
WITH j AS (
  SELECT p.*, c.primary_device_id, c.prefecture AS cust_pref
  FROM {SRC}.t_payments p LEFT JOIN {SRC}.m_customers c USING (customer_id)
)
SELECT 'overall' dim, CAST(NULL AS STRING) val, COUNT(*) n, ROUND(AVG(CAST(is_fraud AS INT)),4) fraud_rate FROM j
UNION ALL SELECT 'device_mismatch', CAST(device_id<>primary_device_id AS STRING), COUNT(*), ROUND(AVG(CAST(is_fraud AS INT)),4) FROM j GROUP BY device_id<>primary_device_id
UNION ALL SELECT 'geo_mismatch', CAST(transaction_prefecture<>cust_pref AS STRING), COUNT(*), ROUND(AVG(CAST(is_fraud AS INT)),4) FROM j GROUP BY transaction_prefecture<>cust_pref
ORDER BY dim, val
"""))

# COMMAND ----------

# DBTITLE 1,テーブル・カラムの説明文をUnity Catalogに登録
# =============================================================
# 各テーブル・カラムの説明文をUnity Catalogに登録
# =============================================================

def set_table_comment(table_name, comment):
    spark.sql(f"COMMENT ON TABLE {SRC}.{table_name} IS '{comment}'")

def set_column_comments(table_name, column_comments):
    for col, comment in column_comments.items():
        spark.sql(f"ALTER TABLE {SRC}.{table_name} ALTER COLUMN {col} COMMENT '{comment}'")

# --- m_customers ---
set_table_comment("m_customers",
    "通信会社ペイメントサービスの会員情報マスターテーブル。顧客の属性情報（氏名、住所、通信プラン等）に加え、不正検知用の基準値（月間平均利用額、主利用デバイス）を含む。")
set_column_comments("m_customers", {
    "customer_id": "顧客ID（PK）。C + 9桁の数字で一意に識別",
    "last_name": "顧客の姓",
    "first_name": "顧客の名",
    "gender": "性別（M: 男性, F: 女性）",
    "birth_date": "生年月日",
    "prefecture": "登録住所の都道府県。不正検知では決済地との一致判定に使用",
    "registration_date": "サービス登録日",
    "telecom_plan": "契約中の通信プラン（5G無制限/スタンダード/ライト/オンライン専用等）",
    "customer_status": "会員ステータス（アクティブ/休止/解約）",
    "avg_monthly_spend": "月間平均利用額（円）。不正検知での金額異常判定の基準値として使用",
    "primary_device_id": "主利用デバイスID。不正検知でのデバイス変更検知に使用"
})

# --- m_merchants ---
set_table_comment("m_merchants",
    "加盟店（決済先店舗）情報マスターテーブル。店舗名・業種カテゴリ・所在地を管理。カテゴリは決済金額の妥当性判定に使用。")
set_column_comments("m_merchants", {
    "merchant_id": "加盟店ID（PK）。M + 6桁の数字で一意に識別",
    "category": "業種カテゴリ（コンビニ/スーパー/飲食/ドラッグストア/ECサイト/家電量販/アパレル/交通/エンタメ）",
    "prefecture": "加盟店の所在都道府県",
    "merchant_name": "加盟店名（ブランド名 + 支店番号）"
})

# --- m_payment_methods ---
set_table_comment("m_payment_methods",
    "顧客が登録している決済手段のマスターテーブル。顧客1人あたり平均1.8個の決済手段を保有。QR決済・クレジットカード・iD・デビットカードの4種類。")
set_column_comments("m_payment_methods", {
    "method_id": "決済手段ID（PK）。PM + 8桁の数字で一意に識別",
    "customer_id": "保有顧客ID（FK: m_customers.customer_id）",
    "method_type": "決済手段の種類（QR決済/クレジットカード/iD/デビットカード）",
    "card_number_masked": "マスク済みカード番号（末尾4桁のみ表示）",
    "registered_date": "決済手段の登録日",
    "status": "決済手段のステータス（有効/停止/期限切れ）"
})

# --- t_payments ---
set_table_comment("t_payments",
    "決済トランザクションテーブル（主テーブル）。不正検知の教師ラベル(is_fraud)を含む。約2〜3%が不正取引で、デバイス不一致・地域不一致・加盟店リスク・高額比率・直前24hの失敗ログインに依存して確率的に生成される。")
set_column_comments("t_payments", {
    "payment_id": "決済ID（PK）。PAY + 数字で一意に識別",
    "customer_id": "決済を行った顧客のID（FK: m_customers.customer_id）",
    "merchant_id": "決済先の加盟店ID（FK: m_merchants.merchant_id）",
    "method_id": "使用した決済手段ID（FK: m_payment_methods.method_id）",
    "payment_timestamp": "決済日時。時系列分割や時間帯特徴量の作成に使用",
    "amount": "決済金額（円）",
    "status": "決済ステータス（完了/キャンセル/返金/エラー）",
    "device_type": "決済時に使用したデバイス種別（スマートフォン/PC/タブレット）",
    "device_id": "決済時のデバイスID。主利用デバイスとの一致判定に使用",
    "transaction_prefecture": "決済時の位置情報（都道府県）。登録住所との乖離検知に使用",
    "ip_address_masked": "IPアドレス（上位3オクテットのみ）",
    "is_fraud": "不正決済フラグ（教師ラベル）。True=不正, False=正常。約2〜3%がTrue"
})

# --- t_login_events ---
set_table_comment("t_login_events",
    "ログイン履歴テーブル。アカウント乗っ取り検知のための補助データ。ログイン時のデバイス・地理情報・認証方法・成功可否を記録。取引直前の失敗ログインが時系列特徴量として不正検知に効く。")
set_column_comments("t_login_events", {
    "login_id": "ログインイベントID（PK）。LGN + 12桁の数字で一意に識別",
    "customer_id": "ログインした顧客ID（FK: m_customers.customer_id）",
    "login_timestamp": "ログイン日時",
    "device_id": "ログイン時のデバイスID",
    "device_type": "ログイン時のデバイス種別（スマートフォン/PC/タブレット）",
    "login_prefecture": "ログイン時の位置情報（都道府県）",
    "ip_address_masked": "IPアドレス（上位3オクテットのみ）",
    "is_success": "ログイン成功可否。失敗回数の集計により不正アクセス検知に活用",
    "auth_method": "認証方法（パスワード/生体認証/SMS認証/パスキー）"
})

# --- t_charges ---
set_table_comment("t_charges",
    "チャージ（残高入金）履歴テーブル。QR決済用の残高チャージを記録。金額は1000円刻みの切りの良い値が多い。")
set_column_comments("t_charges", {
    "charge_id": "チャージID（PK）。CHG + 10桁の数字で一意に識別",
    "customer_id": "チャージを行った顧客ID（FK: m_customers.customer_id）",
    "amount": "チャージ金額（円）　1000/2000/3000/5000/10000/20000/30000/50000のいずれか",
    "source": "チャージ元（銀行口座/クレジットカード/ATM/ネットバンキング/オートチャージ）",
    "charge_timestamp": "チャージ実行日時",
    "status": "チャージ結果（成功/失敗）　97%が成功"
})

print("✅ 全テーブル・カラムの説明文をUnity Catalogに登録しました")

# COMMAND ----------

# DBTITLE 1,PK/FK制約の付与
# =============================================================
# PK/FK制約の付与（Databricks の PK/FK は情報提供用。リネージ・最適化に活用）
# 参考: https://docs.databricks.com/aws/ja/tables/constraints
# =============================================================

def add_pk(table_name, pk_columns):
    """PK制約を追加。まずNOT NULLを設定し、その後PKを宣言。"""
    full_name = f"{SRC}.{table_name}"
    constraint_name = f"{table_name}_pk"
    for col in pk_columns:
        spark.sql(f"ALTER TABLE {full_name} ALTER COLUMN {col} SET NOT NULL")
    pk_cols_str = ", ".join(pk_columns)
    spark.sql(f"ALTER TABLE {full_name} DROP CONSTRAINT IF EXISTS {constraint_name}")
    spark.sql(f"ALTER TABLE {full_name} ADD CONSTRAINT {constraint_name} PRIMARY KEY({pk_cols_str})")
    print(f"  PK: {full_name} ({pk_cols_str})")


def add_fk(child_table, fk_columns, parent_table):
    """FK制約を追加。"""
    child_full = f"{SRC}.{child_table}"
    parent_full = f"{SRC}.{parent_table}"
    fk_cols_str = ", ".join(fk_columns)
    constraint_name = f"{child_table}_{fk_columns[0]}_fk"
    spark.sql(f"ALTER TABLE {child_full} DROP CONSTRAINT IF EXISTS {constraint_name}")
    spark.sql(f"ALTER TABLE {child_full} ADD CONSTRAINT {constraint_name} FOREIGN KEY({fk_cols_str}) REFERENCES {parent_full}")
    print(f"  FK: {child_full}.{fk_cols_str} -> {parent_full}")


print("■ PRIMARY KEY 制約の追加")
print("=" * 50)
add_pk("m_customers", ["customer_id"])
add_pk("m_merchants", ["merchant_id"])
add_pk("m_payment_methods", ["method_id"])
add_pk("t_payments", ["payment_id"])
add_pk("t_login_events", ["login_id"])
add_pk("t_charges", ["charge_id"])

print("\n■ FOREIGN KEY 制約の追加")
print("=" * 50)
# m_payment_methods -> m_customers
add_fk("m_payment_methods", ["customer_id"], "m_customers")
# t_payments -> m_customers, m_merchants, m_payment_methods
add_fk("t_payments", ["customer_id"], "m_customers")
add_fk("t_payments", ["merchant_id"], "m_merchants")
add_fk("t_payments", ["method_id"], "m_payment_methods")
# t_login_events -> m_customers
add_fk("t_login_events", ["customer_id"], "m_customers")
# t_charges -> m_customers
add_fk("t_charges", ["customer_id"], "m_customers")

print("\n✅ 全てのPK/FK制約を付与しました")