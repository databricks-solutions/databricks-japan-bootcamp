# Databricks notebook source
# MAGIC %md
# MAGIC # 10. Bronze：Auto Loader による取り込み
# MAGIC
# MAGIC 共有 Volume に届いた Parquet を **Auto Loader（cloudFiles）** で増分取り込みし、Bronze ファクトテーブルを作る。
# MAGIC - ソース：共有 landing Volume（全員共通・読み取り）
# MAGIC - チェックポイント：各自専用 Volume
# MAGIC - 取り込み時刻を**東京タイムゾーン**で付与し、増分取り込みを確認する
# MAGIC - Bronze テーブルにも **Liquid Clustering** を設定する

# COMMAND ----------

# MAGIC %md
# MAGIC ## 初期セットアップの読み込み
# MAGIC セットアップノートブックを実行し、共通変数（`catalog` / `schema` / `bp` / `shared_landing` / `checkpoint_base` など）を引き継ぐ。
# MAGIC （事前に `05_setup` を一度実行しておくこと）

# COMMAND ----------

# MAGIC %run ./05_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Auto Loader 取り込み関数
# MAGIC `cloudFiles` で新規ファイルのみを増分検出する。取り込み時刻を東京 TZ で付与し、
# MAGIC 結合キー（`customer_id`）で **Liquid Clustering** を設定する。

# COMMAND ----------

def ingest_fact(table: str):
    src  = f"{shared_landing}/{table}/"          # 共有 Volume のソースパス（全員共通）
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## ファクトの取り込み ＋ 件数確認
# MAGIC
# MAGIC このセルを、次の流れで **2 回** 実行する。**同じコードを 2 回実行するのがポイント**。
# MAGIC
# MAGIC 1. **【1 回目】** まずこのセルを実行し、初期データを取り込む（件数をメモしておく）
# MAGIC 2. **【講師の作業を待つ】** 講師が増分データ（7 月分）を共有 Volume に追加する
# MAGIC 3. **【2 回目】** 講師の追加後、**このセルをもう一度**実行する（コードは変更しない）
# MAGIC
# MAGIC → 2 回目では、1 回目に取り込んだデータは再処理されず、**追加された増分だけ**が取り込まれる。

# COMMAND ----------

# 4 ファクトを取り込み（1回目/2回目とも同じコード）
for t in ["t_payments", "t_point_transactions", "t_charges", "t_login_events"]:
    ingest_fact(t)

# 件数確認（1回目実行後の件数はメモしておく）
print("=== Bronze ファクト件数 ===")
for t in ["t_payments", "t_point_transactions", "t_charges", "t_login_events"]:
    print(f"bronze_{t}: {spark.table(f'{bp}.bronze_{t}').count():,} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ★ 増分取り込みの確認（取り込み時刻ベース）
# MAGIC 2 回目の取り込み後にこのセルを実行する。取り込み時刻（`_ingested_at`, 東京 TZ）を分単位でグルーピングし、
# MAGIC **1 回目の分は再処理されず、2 回目は追加分だけ増えている**ことを確認する。

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

print("✅ Bronze 取り込み 完了")