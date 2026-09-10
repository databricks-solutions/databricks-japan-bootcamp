# Databricks notebook source
# MAGIC %md
# MAGIC # サンプルデータ生成（教材メンテナンス用）
# MAGIC
# MAGIC **参加者は実行しません。** リポジトリ同梱の `sample_data/` を再生成するための管理用ノートブックです。
# MAGIC 縮小件数・各テーブル単一ファイルで、決済不正検知のサンプルを生成します。
# MAGIC
# MAGIC 出力先: `/Volumes/workspace/de_gen_tmp/out/{master, landing_initial, landing_incremental}/<table>/`
# MAGIC 実行後、この Volume の Parquet をダウンロードして `sample_data/` に配置・コミットします。
# %pip
# MAGIC %pip install dbldatagen
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import dbldatagen as dg
from pyspark.sql import functions as F
from pyspark.sql.types import *

CAT="workspace"; SCH="de_gen_tmp"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CAT}.{SCH}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CAT}.{SCH}.out")
OUT=f"/Volumes/{CAT}/{SCH}/out"

# 縮小件数
num_customers=2000; num_merchants=200; num_payment_methods=int(num_customers*1.8)
num_payments=30000; num_points=6000; num_charges=800; num_logins=6000
fraud_rate=0.10; date_start="2026-01-01"; date_end="2026-06-30"

prefectures=["東京都","神奈川県","大阪府","愛知県","埼玉県","千葉県","兵庫県","北海道","福岡県","静岡県","京都府","広島県","宮城県","新潟県","長野県","岐阜県","群馬県","栃木県","岡山県","福島県"]
pw=[14,9,9,7,7,6,5,5,5,4,3,3,2,2,2,2,2,2,2,2]
telecom_plans=["5G無制限プラン","スタンダードプラン","ライト3GB","ライト6GB","ライト9GB","オンライン専用プラン"]; plan_w=[15,20,20,15,10,20]
cust_status=["アクティブ","休止","解約"]; status_w=[85,10,5]
device_types=["スマートフォン","PC","タブレット"]; dtw=[70,20,10]

def one(df, path):
    df.repartition(1).write.mode("overwrite").parquet(path)

# COMMAND ----------
# master: customers
df_customers=(dg.DataGenerator(spark,name="m_customers",rows=num_customers,seedColumnName="_seed")
 .withColumn("customer_id",StringType(),expr="format_string('C%09d', _seed)")
 .withColumn("last_name",StringType(),values=["佐藤","鈴木","高橋","田中","伊藤","渡辺","山本","中村","小林","加藤"],random=True)
 .withColumn("first_name",StringType(),values=["太郎","次郎","健太","翔太","蓮","美咲","結衣","陽菜","美月","優子"],random=True)
 .withColumn("gender",StringType(),values=["M","F"],weights=[50,50],random=True)
 .withColumn("birth_date",DateType(),begin="1960-01-01",end="2005-12-31",random=True)
 .withColumn("prefecture",StringType(),values=prefectures,weights=pw,random=True)
 .withColumn("registration_date",DateType(),begin="2019-01-01",end=date_start,random=True)
 .withColumn("telecom_plan",StringType(),values=telecom_plans,weights=plan_w,random=True)
 .withColumn("customer_status",StringType(),values=cust_status,weights=status_w,random=True)
 .withColumn("avg_monthly_spend",IntegerType(),minValue=5000,maxValue=80000,random=True)
 .withColumn("primary_device_id",StringType(),expr="format_string('DEV%010d', _seed)")
 ).build().drop("_seed")
one(df_customers, f"{OUT}/master/m_customers/")

merchant_cat=["コンビニ","スーパー","飲食","ドラッグストア","ECサイト","家電量販","アパレル","交通","エンタメ"]; cw=[20,15,20,10,15,5,5,5,5]
df_merchants=(dg.DataGenerator(spark,name="m_merchants",rows=num_merchants,seedColumnName="_seed")
 .withColumn("merchant_id",StringType(),expr="format_string('M%06d', _seed)")
 .withColumn("category",StringType(),values=merchant_cat,weights=cw,random=True)
 .withColumn("prefecture",StringType(),values=prefectures,weights=pw,random=True)
 ).build().drop("_seed")
df_merchants=df_merchants.withColumn("merchant_name",F.concat(F.col("category"),F.lit("店"),(F.abs(F.hash("merchant_id"))%300+1).cast("string"),F.lit("号")))
one(df_merchants, f"{OUT}/master/m_merchants/")

method_types=["QR決済","クレジットカード","iD","デビットカード"]; mw=[35,30,20,15]
df_pm=(dg.DataGenerator(spark,name="m_payment_methods",rows=num_payment_methods,seedColumnName="_seed")
 .withColumn("method_id",StringType(),expr="format_string('PM%08d', _seed)")
 .withColumn("customer_id",StringType(),expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
 .withColumn("method_type",StringType(),values=method_types,weights=mw,random=True)
 .withColumn("card_number_masked",StringType(),expr="concat('****-****-****-', format_string('%04d', cast(floor(rand()*10000) as int)))")
 .withColumn("registered_date",DateType(),begin="2019-01-01",end=date_start,random=True)
 .withColumn("status",StringType(),values=["有効","停止","期限切れ"],weights=[90,5,5],random=True)
 ).build().drop("_seed")
one(df_pm, f"{OUT}/master/m_payment_methods/")
print("master done")

# COMMAND ----------
# fact: payments (initial) with fraud patterns
def gen_payments(rows, dstart, dend, id_offset):
    ds=(dg.DataGenerator(spark,name="t_payments",rows=rows,seedColumnName="_seed")
     .withColumn("payment_id",StringType(),expr=f"format_string('PAY%012d', _seed + {id_offset})")
     .withColumn("customer_id",StringType(),expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
     .withColumn("merchant_id",StringType(),expr=f"format_string('M%06d', cast(floor(rand()*{num_merchants}) as int))")
     .withColumn("method_id",StringType(),expr=f"format_string('PM%08d', cast(floor(rand()*{num_payment_methods}) as int))")
     .withColumn("payment_timestamp",TimestampType(),begin=dstart+" 00:00:00",end=dend+" 23:59:59",random=True)
     .withColumn("amount",IntegerType(),minValue=100,maxValue=50000,random=True)
     .withColumn("status",StringType(),values=["完了","キャンセル","返金","エラー"],weights=[92,4,3,1],random=True)
     .withColumn("device_type",StringType(),values=device_types,weights=dtw,random=True)
     .withColumn("device_id",StringType(),expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
     .withColumn("transaction_prefecture",StringType(),values=prefectures,weights=pw,random=True)
     .withColumn("ip_address_masked",StringType(),expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
     ).build().drop("_seed")
    ds=ds.withColumn("is_fraud",(F.rand()<fraud_rate))
    ds=ds.withColumn("_pat",F.when(~F.col("is_fraud"),F.lit("normal"))
        .when(F.rand()<0.30,F.lit("深夜大量")).when(F.rand()<0.36,F.lit("地理異常"))
        .when(F.rand()<0.44,F.lit("高額異常")).when(F.rand()<0.60,F.lit("カードテスト")).otherwise(F.lit("乗っ取り")))
    ds=ds.join(df_customers.select("customer_id",F.col("prefecture").alias("home_pref"),"avg_monthly_spend","primary_device_id"),"customer_id","left")
    ds=ds.withColumn("payment_timestamp",F.when(F.col("_pat")=="深夜大量",F.col("payment_timestamp").cast("date").cast("timestamp")+F.expr("make_interval(0,0,0,0,cast(floor(rand()*3+2) as int),cast(floor(rand()*60) as int),0)")).otherwise(F.col("payment_timestamp")))
    _remote=["北海道","青森県","沖縄県","鹿児島県","岩手県","秋田県","山形県","宮崎県"]
    ds=ds.withColumn("transaction_prefecture",F.when(F.col("_pat")=="地理異常",F.array(*[F.lit(p) for p in _remote]).getItem((F.abs(F.hash("payment_id"))%len(_remote)))).when(~F.col("is_fraud"),F.when(F.rand()<0.8,F.col("home_pref")).otherwise(F.col("transaction_prefecture"))).otherwise(F.col("transaction_prefecture")))
    ds=ds.withColumn("amount",F.when(F.col("_pat")=="高額異常",F.least((F.col("avg_monthly_spend")*(F.rand()*5+5)/30).cast("int"),F.lit(500000))).otherwise(F.col("amount")))
    ds=ds.withColumn("amount",F.when(F.col("_pat")=="カードテスト",(F.rand()*400+100).cast("int")).otherwise(F.col("amount")))
    ds=ds.withColumn("device_id",F.when(F.col("_pat")=="乗っ取り",F.concat(F.lit("DEV_NEW_"),F.substring(F.md5("payment_id"),1,8))).when((~F.col("is_fraud"))&(F.rand()<0.9),F.col("primary_device_id")).otherwise(F.col("device_id")))
    return ds.drop("_pat","home_pref","avg_monthly_spend","primary_device_id")

one(gen_payments(num_payments,date_start,date_end,0), f"{OUT}/landing_initial/t_payments/")
one(gen_payments(6000,"2026-07-01","2026-07-07",num_payments), f"{OUT}/landing_incremental/t_payments/")
print("payments done")

# COMMAND ----------
# points / charges / logins (initial + incremental)
def gen_points(rows,dstart,dend,off):
    d=(dg.DataGenerator(spark,name="pt",rows=rows,seedColumnName="_seed")
     .withColumn("point_txn_id",StringType(),expr=f"format_string('PT%012d', _seed + {off})")
     .withColumn("customer_id",StringType(),expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
     .withColumn("payment_id",StringType(),expr=f"format_string('PAY%012d', cast(floor(rand()*{num_payments}) as int))")
     .withColumn("txn_type",StringType(),values=["付与","利用","失効"],weights=[70,25,5],random=True)
     .withColumn("points",IntegerType(),minValue=1,maxValue=500,random=True)
     .withColumn("txn_timestamp",TimestampType(),begin=dstart+" 00:00:00",end=dend+" 23:59:59",random=True)
     ).build().drop("_seed")
    d=d.withColumn("points",F.when(F.col("txn_type").isin("利用","失効"),-F.abs("points")).otherwise(F.abs("points")))
    return d.withColumn("payment_id",F.when(F.col("txn_type")=="失効",F.lit(None)).otherwise(F.col("payment_id")))
one(gen_points(num_points,date_start,date_end,0), f"{OUT}/landing_initial/t_point_transactions/")
one(gen_points(1200,"2026-07-01","2026-07-07",100000), f"{OUT}/landing_incremental/t_point_transactions/")

def gen_charges(rows,dstart,dend,off):
    return (dg.DataGenerator(spark,name="chg",rows=rows,seedColumnName="_seed")
     .withColumn("charge_id",StringType(),expr=f"format_string('CHG%010d', _seed + {off})")
     .withColumn("customer_id",StringType(),expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
     .withColumn("amount",IntegerType(),values=[1000,2000,3000,5000,10000,20000,30000,50000],weights=[15,15,15,20,15,10,5,5],random=True)
     .withColumn("source",StringType(),values=["銀行口座","クレジットカード","ATM","ネットバンキング","オートチャージ"],weights=[30,25,15,10,20],random=True)
     .withColumn("charge_timestamp",TimestampType(),begin=dstart+" 00:00:00",end=dend+" 23:59:59",random=True)
     .withColumn("status",StringType(),values=["成功","失敗"],weights=[97,3],random=True)
     ).build().drop("_seed")
one(gen_charges(num_charges,date_start,date_end,0), f"{OUT}/landing_initial/t_charges/")
one(gen_charges(150,"2026-07-01","2026-07-07",100000), f"{OUT}/landing_incremental/t_charges/")

def gen_logins(rows,dstart,dend,off):
    return (dg.DataGenerator(spark,name="lg",rows=rows,seedColumnName="_seed")
     .withColumn("login_id",StringType(),expr=f"format_string('LGN%012d', _seed + {off})")
     .withColumn("customer_id",StringType(),expr=f"format_string('C%09d', cast(floor(rand()*{num_customers}) as int))")
     .withColumn("login_timestamp",TimestampType(),begin=dstart+" 00:00:00",end=dend+" 23:59:59",random=True)
     .withColumn("device_id",StringType(),expr=f"format_string('DEV%010d', cast(floor(rand()*{num_customers*2}) as int))")
     .withColumn("device_type",StringType(),values=device_types,weights=dtw,random=True)
     .withColumn("login_prefecture",StringType(),values=prefectures,weights=pw,random=True)
     .withColumn("ip_address_masked",StringType(),expr="concat(cast(cast(floor(rand()*200+1) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.',cast(cast(floor(rand()*256) as int) as string),'.***')")
     .withColumn("is_success",BooleanType(),values=[True,False],weights=[92,8],random=True)
     .withColumn("auth_method",StringType(),values=["パスワード","生体認証","SMS認証","パスキー"],weights=[40,30,20,10],random=True)
     ).build().drop("_seed")
one(gen_logins(num_logins,date_start,date_end,0), f"{OUT}/landing_initial/t_login_events/")
one(gen_logins(1200,"2026-07-01","2026-07-07",100000), f"{OUT}/landing_incremental/t_login_events/")
print("all facts done")

import json
dbutils.notebook.exit(json.dumps({"out":OUT}))
