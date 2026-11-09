# Databricks notebook source
# MAGIC %md
# MAGIC # 01 Bronze｜取り込む
# MAGIC
# MAGIC **型のどこか**：**取り込む** → AI で取り出す → 確かめる → つなぐ
# MAGIC
# MAGIC 音声・画像・帳票の3形式を、形式を問わず **1つのテーブル**（Bronze）に取り込みます。ファイルの中身（バイナリ）とメタデータ（パス・サイズ）を、1行＝1ファイルで持ちます。
# MAGIC この段階では中身を解釈しません。LLM も使いません。
# MAGIC
# MAGIC ### なぜ最初に1つのテーブルに取り込むのか
# MAGIC
# MAGIC - 形式が違っても、この後の工程はすべて「Bronze から読む」という同じ入口になります。
# MAGIC - 「何が・何件・どのくらいの量届いたか」を SQL で数えられます（棚卸し）。
# MAGIC - 元のファイルがテーブルに残るので、後の工程をやり直すときもファイルを探し直さずに済みます。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Auto Loader で取り込む
# MAGIC
# MAGIC [Auto Loader](https://docs.databricks.com/aws/ja/ingestion/cloud-object-storage/auto-loader/) は、フォルダに届いたファイルを取り込む仕組みです。取り込んだファイルをチェックポイント（`_checkpoints/bronze`）に記録するため、**次に実行したときは、新しく届いたファイルだけ** を取り込みます。
# MAGIC
# MAGIC コードの流れ：
# MAGIC
# MAGIC 1. `readStream.format("cloudFiles")`：Auto Loader で `landing/` の下（`audio/`・`image/`・`form/` を含む）を読む
# MAGIC 2. `select(...)`：パスから形式（どのフォルダか）と受付番号（ファイル名の `case_XX`）を取り出して列にする
# MAGIC 3. `writeStream ... toTable(BRONZE)`：Bronze テーブルに追記する
# MAGIC
# MAGIC `trigger(availableNow=True)` は「今あるファイルをすべて処理したら止まる」実行の仕方です。常に動き続ける処理ではなく、ふつうのバッチ処理と同じように終わります。

# COMMAND ----------

from pyspark.sql import functions as F

# 取り込む前の行数（今回何件取り込んだかを数えるため）
before = spark.table(BRONZE).count() if spark.catalog.tableExists(BRONZE) else 0

query = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "binaryFile")       # ファイルを中身（バイナリ）ごと1行として読む
    .load(LANDING)
    .select(
        "path",                                                                              # ファイルのパス
        F.regexp_extract("path", r"/landing/(audio|image|form)/", 1).alias("modality"),      # どのフォルダに届いたか＝形式
        F.regexp_extract("path", r"(case_\d+)", 1).alias("case_id"),                          # ファイル名から受付番号
        "length",                                                                            # ファイルサイズ（バイト）
        "content",                                                                           # ファイルの中身
        F.current_timestamp().alias("ingested_at"),                                          # 取り込んだ時刻
    )
    .writeStream
    .option("checkpointLocation", f"{CHECKPOINT}/bronze")   # 処理済みのファイルの記録
    .trigger(availableNow=True)                             # 今あるファイルを処理して止まる
    .toTable(BRONZE)
)
query.awaitTermination()   # 取り込みが終わるまで待つ
print("今回取り込んだファイル数:", spark.table(BRONZE).count() - before)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 棚卸し：何が・何件・どのくらいの量あるか
# MAGIC
# MAGIC 形式ごとの件数と合計サイズです。1回目は各形式5件になります。
# MAGIC 本番で大量のファイルを扱うときは、この棚卸しが、処理にかかる時間と費用を見積もる出発点になります。

# COMMAND ----------

display(spark.sql(f"""
SELECT modality AS `形式`, count(*) AS `件数`, round(sum(length) / 1024 / 1024, 2) AS `合計MB`,
       max(ingested_at) AS `最後に取り込んだ時刻`
FROM {BRONZE} GROUP BY modality ORDER BY modality"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze テーブルの中身
# MAGIC
# MAGIC 1行＝1ファイルです。`content` 列（ファイルの中身）は大きいので、ここでは表示から外しています。

# COMMAND ----------

display(spark.table(BRONZE).select("case_id", "modality", "length", "path", "ingested_at").orderBy("case_id", "modality"))
