# Databricks notebook source
# MAGIC %md
# MAGIC # 10. Bronze：Auto Loader による取り込み
# MAGIC
# MAGIC `05_setup` が `landing` Volume に生成した Parquet を **Auto Loader（cloudFiles）** で取り込み、Bronze ファクトテーブルを作る。
# MAGIC さらに **増分データの生成 → 再取り込み** までこのノートブック内で完結し、Auto Loader の増分（Exactly-once）を体験する。
# MAGIC - ソース：自分の `landing` Volume（`workspace.de_workshop.landing`）
# MAGIC - チェックポイント：自分の `checkpoints` Volume
# MAGIC - 取り込み時刻を**東京タイムゾーン**で付与し、増分取り込みを確認する
# MAGIC - Bronze テーブルにも **Liquid Clustering** を設定する

# COMMAND ----------

# MAGIC %md
# MAGIC ## 初期セットアップの読み込み
# MAGIC `05_setup` を実行し、共通変数（`catalog` / `schema` / `bp` / `landing` / `checkpoint_base` / `num_*` など）を引き継ぐ。
# MAGIC （事前に `05_setup` を一度実行し、初期データが生成済みであること）

# COMMAND ----------

# MAGIC %run ./05_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Auto Loader 取り込み関数
# MAGIC `cloudFiles` で新規ファイルのみを増分検出する。取り込み時刻を東京 TZ で付与し、
# MAGIC 結合キー（`customer_id`）で **Liquid Clustering** を設定する。

# COMMAND ----------

def ingest_fact(table: str):
    src  = f"{landing}/{table}/"                 # 自分の landing Volume（05_setup が生成）
    ckpt = f"{checkpoint_base}/{table}/"         # 自分専用のチェックポイント
    (spark.readStream
        .format("cloudFiles")                                        # ★Auto Loader（増分・自動検出）
        .option("cloudFiles.format", "parquet")                      # 取り込むファイル形式
        .option("cloudFiles.schemaLocation", ckpt)                   # スキーマ情報の保存先
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")   # 新規列を自動追加（スキーマ進化）
        .load(src)
        # ★取り込み時刻を東京タイムゾーンで付与（増分取り込みの確認に使用）
        .withColumn("_ingested_at", F.from_utc_timestamp(F.current_timestamp(), "Asia/Tokyo"))
        .withColumn("_source_file", F.col("_metadata.file_path"))    # 由来ファイルパスを記録
     .writeStream
        .clusterBy("customer_id")                                    # ★Bronze も Liquid Clustering（結合キー）
        .option("checkpointLocation", ckpt)                          # ★チェックポイント（既読管理＝冪等性）
        .trigger(availableNow=True)                                  # ★到着分を処理して停止（バッチ的）
        .toTable(f"{bp}.bronze_{table}")                             # 自分のスキーマに Bronze テーブル出力
     .awaitTermination())                                            # 取り込み完了まで待機

FACTS = ["t_payments", "t_point_transactions", "t_charges", "t_login_events"]

def show_counts(label: str):
    print(f"=== Bronze ファクト件数（{label}）===")
    for t in FACTS:
        print(f"bronze_{t}: {spark.table(f'{bp}.bronze_{t}').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 【1 回目】初期データの取り込み
# MAGIC `landing` の各ファクト（初期データ）を取り込み、件数を確認する（メモしておく）。

# COMMAND ----------

for t in FACTS:
    ingest_fact(t)
show_counts("1回目・初期データ")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 【増分データを生成】7 月分を `batch=20260707/` に追加
# MAGIC Auto Loader の増分取り込みを体験するため、**このノートブック内で**増分データ（7 月分）を生成し、
# MAGIC 各ファクトの `landing/<table>/batch=20260707/` サブフォルダに **Parquet** で出力する。
# MAGIC （`05_setup` と同じ採番母数を使い、外部キーは既存マスターの範囲内で採番。`admin/01` の実行は不要）

# COMMAND ----------

# --- 増分パラメータ（初期生成 05_setup と同じ母数を使用）---
BATCH = "20260707"
INC_START = "2026-07-01 00:00:00"
INC_END   = "2026-07-07 23:59:59"
inc_payments, inc_points, inc_charges, inc_logins = 10000, 2000, 200, 2000

_ibase = F.unix_timestamp(F.lit(INC_START))
_ispan = F.unix_timestamp(F.lit(INC_END)) - F.unix_timestamp(F.lit(INC_START))
_PREF = ["東京都","神奈川県","大阪府","愛知県","埼玉県","千葉県","兵庫県","北海道","福岡県","静岡県",
         "京都府","広島県","宮城県","新潟県","長野県","岐阜県","群馬県","栃木県","岡山県","福島県"]
_DEV  = ["スマートフォン","PC","タブレット"]
_ip = F.concat(F.floor(F.rand()*200+1).cast("string"), F.lit("."),
               F.floor(F.rand()*256).cast("string"), F.lit("."),
               F.floor(F.rand()*256).cast("string"), F.lit(".***"))

# --- 増分：決済（payment_id は初期分 num_payments のオフセットで衝突回避、7 月日付）---
inc_pay = (spark.range(inc_payments)
    .withColumn("payment_id", F.format_string("PAY%012d", F.col("id") + num_payments))
    .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
    .withColumn("merchant_id", F.format_string("M%06d", F.floor(F.rand()*num_merchants).cast("long")))
    .withColumn("method_id", F.format_string("PM%08d", F.floor(F.rand()*num_payment_methods).cast("long")))
    .withColumn("payment_timestamp", F.to_timestamp(F.from_unixtime(_ibase + (F.rand()*_ispan).cast("long"))))
    .withColumn("amount", (F.rand()*49900+100).cast("int"))
    .withColumn("status", _pick(F.col("id"), "ipst", ["完了","完了","完了","完了","キャンセル","返金","エラー"]))
    .withColumn("device_type", _pick(F.col("id"), "idt", _DEV))
    .withColumn("device_id", F.format_string("DEV%010d", F.floor(F.rand()*num_customers*2).cast("long")))
    .withColumn("transaction_prefecture", _pick(F.col("id"), "itp", _PREF))
    .withColumn("ip_address_masked", _ip)
    .withColumn("is_fraud", F.rand() < fraud_rate)
    .drop("id"))
inc_pay.repartition(2).write.mode("overwrite").parquet(f"{landing}/t_payments/batch={BATCH}/")

# --- 増分：ポイント ---
inc_pts = (spark.range(inc_points)
    .withColumn("point_txn_id", F.format_string("PT%012d", F.col("id") + 100000))
    .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
    .withColumn("payment_id", F.format_string("PAY%012d", F.floor(F.rand()*num_payments).cast("long")))
    .withColumn("txn_type", _pick(F.col("id"), "ipt", ["付与","付与","付与","利用","失効"]))
    .withColumn("points", (F.rand()*499+1).cast("int"))
    .withColumn("txn_timestamp", F.to_timestamp(F.from_unixtime(_ibase + (F.rand()*_ispan).cast("long"))))
    .drop("id"))
inc_pts = inc_pts.withColumn("points", F.when(F.col("txn_type").isin("利用","失効"), -F.abs("points")).otherwise(F.abs("points")))
inc_pts = inc_pts.withColumn("payment_id", F.when(F.col("txn_type")=="失効", F.lit(None)).otherwise(F.col("payment_id")))
inc_pts.repartition(1).write.mode("overwrite").parquet(f"{landing}/t_point_transactions/batch={BATCH}/")

# --- 増分：チャージ ---
inc_chg = (spark.range(inc_charges)
    .withColumn("charge_id", F.format_string("CHG%010d", F.col("id") + 100000))
    .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
    .withColumn("amount", _pick(F.col("id"), "ichg", [1000,2000,3000,5000,10000,20000,30000,50000]))
    .withColumn("source", _pick(F.col("id"), "isrc", ["銀行口座","クレジットカード","ATM","ネットバンキング","オートチャージ"]))
    .withColumn("charge_timestamp", F.to_timestamp(F.from_unixtime(_ibase + (F.rand()*_ispan).cast("long"))))
    .withColumn("status", _pick(F.col("id"), "icst", ["成功","成功","成功","失敗"]))
    .drop("id"))
inc_chg.repartition(1).write.mode("overwrite").parquet(f"{landing}/t_charges/batch={BATCH}/")

# --- 増分：ログイン ---
inc_lg = (spark.range(inc_logins)
    .withColumn("login_id", F.format_string("LGN%012d", F.col("id") + 100000))
    .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
    .withColumn("login_timestamp", F.to_timestamp(F.from_unixtime(_ibase + (F.rand()*_ispan).cast("long"))))
    .withColumn("device_id", F.format_string("DEV%010d", F.floor(F.rand()*num_customers*2).cast("long")))
    .withColumn("device_type", _pick(F.col("id"), "ildt", _DEV))
    .withColumn("login_prefecture", _pick(F.col("id"), "ilpref", _PREF))
    .withColumn("ip_address_masked", _ip)
    .withColumn("is_success", F.rand() >= 0.08)
    .withColumn("auth_method", _pick(F.col("id"), "iam", ["パスワード","生体認証","SMS認証","パスキー"]))
    .drop("id"))
inc_lg.repartition(1).write.mode("overwrite").parquet(f"{landing}/t_login_events/batch={BATCH}/")

print(f"増分データ生成 完了（batch={BATCH}）: payments={inc_payments:,} / points={inc_points:,} / charges={inc_charges:,} / logins={inc_logins:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 【2 回目】増分の取り込み（同じコードを再実行）
# MAGIC 取り込み関数は **1 回目とまったく同じ**。Auto Loader はチェックポイントで既読を管理するため、
# MAGIC 1 回目に取り込んだ分は再処理されず、**追加された増分だけ**が取り込まれる（Exactly-once）。

# COMMAND ----------

for t in FACTS:
    ingest_fact(t)
show_counts("2回目・増分反映後")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ★ 増分取り込みの確認
# MAGIC 取り込み時刻（`_ingested_at`, 東京 TZ）と由来ファイルで、**1 回目分は再処理されず 2 回目は増分だけ増えた**ことを確認する。

# COMMAND ----------

# 取り込みバッチ（分単位）ごとの件数とデータ期間を対比
(spark.table(f"{bp}.bronze_t_payments")
    .withColumn("ingest_batch", F.date_trunc("minute", F.col("_ingested_at")))  # 取り込み実行回の塊
    .groupBy("ingest_batch")
    .agg(F.count("*").alias("取り込み件数"),
         F.min("payment_timestamp").alias("データ最古"),
         F.max("payment_timestamp").alias("データ最新"))
    .orderBy("ingest_batch")
    .show(truncate=False))

# 由来ファイルが増分バッチ(batch=)由来かどうかの内訳
(spark.table(f"{bp}.bronze_t_payments")
    .groupBy(F.col("_source_file").contains("batch=").alias("増分バッチ由来"))
    .count().show(truncate=False))

print("✅ Bronze 取り込み（初期＋増分）完了")
