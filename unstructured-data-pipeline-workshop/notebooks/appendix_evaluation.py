# Databricks notebook source
# MAGIC %md
# MAGIC # 付録｜評価：正解データとの突き合わせ
# MAGIC
# MAGIC **流れのどこか**：取り込む → AI で取り出す → **確かめる** → つなぐ
# MAGIC
# MAGIC 04 で見積書から取り出した値を、正解データ（`data/ground_truth/estimate_answers.json`。見積書に実際に書いた値）と項目ごとに突き合わせ、どの項目がどのくらい正しく取れているかを数えます。
# MAGIC
# MAGIC ### なぜ正解データで測るのか
# MAGIC
# MAGIC - 04 で見たとおり、`ai_extract` の信頼度は、取り出した値が正しいかどうかの保証になりません。品質は、正解と比べて測る必要があります。
# MAGIC - スキーマの説明・モデル・関数のバージョンを変えたときに、同じ正解データで比べれば、変更で良くなったか悪くなったかが数字で分かります。
# MAGIC
# MAGIC 04 を実行したあとに実行してください。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 正解データと突き合わせる
# MAGIC
# MAGIC 1. 正解データの JSON を読み、比べる項目だけのテーブルにします。
# MAGIC 2. Silver（04 の結果）と `case_id` で結合します。
# MAGIC 3. 項目ごとに、取り出した値と正解が一致するかを true / false にします。空白の有無（「小林 直子」と「小林直子」など）は区別しません。

# COMMAND ----------

import json
from pyspark.sql import functions as F

FIELDS = ["estimate_no", "estimate_date", "accident_date", "customer", "shop", "subtotal", "tax", "total"]

# 1. 正解データを読む（比べやすいよう、値はすべて文字列にそろえる）
with open(f"{DATA_DIR}/ground_truth/estimate_answers.json", encoding="utf-8") as f:
    answers = json.load(f)
truth = spark.createDataFrame([
    {k: (str(v) if v is not None else None) for k, v in a.items() if k in ["case_id", *FIELDS]}
    for a in answers])

# 2. 04 の結果と結合する
got = spark.table(SILVER_FORM).select("case_id", "min_confidence", *FIELDS)
cmp = got.alias("g").join(truth.alias("t"), "case_id")

# 3. 項目ごとに一致するかを判定する（空白は取り除いてから比べる）
checks = cmp.select("case_id", "g.min_confidence",
                    *[(F.regexp_replace(F.col(f"g.{f}").cast("string"), r"\s", "") ==
                       F.regexp_replace(F.col(f"t.{f}"), r"\s", "")).alias(f) for f in FIELDS])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 項目ごとの正解率
# MAGIC
# MAGIC 項目ごとに、正解と一致した案件の割合（%）です。100 に届かない項目があれば、その項目のスキーマの説明（`description`）を見直す手がかりになります。

# COMMAND ----------

display(checks.select([F.round(F.avg(F.col(f).cast("int")) * 100, 1).alias(f) for f in FIELDS]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 案件ごとの結果と信頼度
# MAGIC
# MAGIC `all_correct` は、すべての項目が正解と一致した案件です。`all_correct` が false の案件と true の案件とで、信頼度（`min_confidence`）に差があるかを見てください。

# COMMAND ----------

display(checks.withColumn("all_correct", F.expr(" AND ".join(FIELDS))).orderBy("case_id"))
