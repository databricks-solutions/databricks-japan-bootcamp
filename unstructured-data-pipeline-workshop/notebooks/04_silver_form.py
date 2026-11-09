# Databricks notebook source
# MAGIC %md
# MAGIC # 04 Silver｜見積書から取り出し、確かめる
# MAGIC
# MAGIC **型のどこか**：取り込む → **AI で取り出す → 確かめる** → つなぐ
# MAGIC
# MAGIC 修理見積書（PDF と、手書きの見積書をスキャンした画像）から、見積番号・日付・工場・明細・金額を取り出します。そのうえで、計算の検算で「人が確認すべき見積書」を振り分けます。
# MAGIC
# MAGIC | | この工程 |
# MAGIC |---|---|
# MAGIC | 手段 | [`ai_parse_document`](https://docs.databricks.com/aws/ja/sql/language-manual/functions/ai_parse_document)（文書を読み、文字と表の構造を取り出す）→ [`ai_extract`](https://docs.databricks.com/aws/ja/sql/language-manual/functions/ai_extract)（取り出したい項目をスキーマで指定して取り出す。version 2.1 は項目ごとの信頼度も返す） |
# MAGIC | なぜこの手段か | 帳票の読み取りと項目の取り出しに特化した関数で、指示文を書かずにスキーマだけで済む。PDF も画像も同じ関数で読める |
# MAGIC | 課金 | AI Functions の課金（`ai_parse_document` はページ数・大きさ・複雑さ、`ai_extract` は入力件数で決まる DBU） |

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 取り出す項目を決める
# MAGIC
# MAGIC `ai_extract` に渡すスキーマです。項目名ごとに型（`string`・`integer`・`enum`・`array` など）と説明（`description`）を書きます。
# MAGIC
# MAGIC - **説明** は、取り出し方の指示として使われます。日付を西暦の `YYYY-MM-DD` に直す、宛名から「様」を除く、といった指定もここに書きます。
# MAGIC - **`enum`** の項目（損傷の位置）は、02・03 と同じ選択肢から答えが返ります。
# MAGIC - **`array`** の項目（明細）は、見積書の表の各行を、1行ずつの組（作業内容・金額）として取り出します。

# COMMAND ----------

import json

EXTRACT_SCHEMA = json.dumps({
    "estimate_no": {"type": "string", "description": "見積番号"},
    "estimate_date": {"type": "string", "description": "見積日。西暦の YYYY-MM-DD 形式に直す（和暦の R8 は 2026 年）"},
    "accident_date": {"type": "string", "description": "事故日。西暦の YYYY-MM-DD 形式に直す。年の記載が無い場合は見積日と同じ年とする"},
    "customer": {"type": "string", "description": "宛名の氏名（「様」は含めない）"},
    "shop": {"type": "string", "description": "見積書を発行した修理工場の名前"},
    "damage_part_text": {"type": "string", "description": "見積書に書かれた損傷部位"},
    "damage_position": {"type": "enum", "labels": DAMAGE_POSITIONS, "description": "損傷の位置。左右は車の進行方向が基準"},
    "items": {"type": "array", "description": "明細の各行", "items": {"type": "object", "properties": {
        "name": {"type": "string", "description": "作業内容・部品名"},
        "amount": {"type": "integer", "description": "金額（円、税抜）"}}}},
    "subtotal": {"type": "integer", "description": "小計（円）"},
    "tax": {"type": "integer", "description": "消費税（円）"},
    "total": {"type": "integer", "description": "合計金額（税込、円）"},
}, ensure_ascii=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 未処理の見積書だけを処理して Silver に追記する
# MAGIC
# MAGIC 1つの SQL で、次の4つを内側から順に行います。
# MAGIC
# MAGIC 1. **未処理の見積書を選ぶ**：Bronze の見積書のうち、Silver に同じ `path` の行が無いもの（`LEFT ANTI JOIN`）
# MAGIC 2. **読む・取り出す**：`ai_parse_document(b.content)` で文書を読み、その結果をそのまま `ai_extract` に渡す。`enableConfidenceScores` で項目ごとの信頼度も返させる
# MAGIC 3. **列に分ける**：`ai_extract` の結果は VARIANT 型（JSON に近い形）で返ります。`ex:response:shop:value` のように `:` でたどって値を取り出します。信頼度は `ex:response:shop:confidence_score` です。明細の金額は `aggregate` で足し上げます
# MAGIC 4. **検算して追記する**：「明細の合計＝小計」かつ「小計＋消費税＝合計」が成り立たなければ、`needs_review`（人が確認する）を true にします
# MAGIC
# MAGIC 出力の `num_inserted_rows` が、今回処理した見積書の件数です。

# COMMAND ----------

# Silver テーブルを用意する（初回だけ作られる）
spark.sql(f"""CREATE TABLE IF NOT EXISTS {SILVER_FORM} (
  case_id STRING, path STRING,
  estimate_no STRING, estimate_date STRING, accident_date STRING, customer STRING, shop STRING,
  damage_part_text STRING, damage_position STRING,
  items_json STRING, items_sum BIGINT, subtotal BIGINT, tax BIGINT, total BIGINT,
  needs_review BOOLEAN, min_confidence DOUBLE,
  error STRING, processed_at TIMESTAMP)""")

# 明細以外の項目の信頼度のうち、いちばん低いもの
scalar = ["estimate_no", "estimate_date", "accident_date", "customer", "shop", "damage_part_text", "damage_position", "subtotal", "tax", "total"]
min_conf = "least(" + ", ".join(f"coalesce(ex:response:{f}:confidence_score::DOUBLE, 1.0)" for f in scalar) + ")"

sql = f"""
INSERT INTO {SILVER_FORM}
-- 4. 検算：明細の合計＝小計、小計＋消費税＝合計 のどちらかが合わなければ、人が確認する
SELECT case_id, path,
       estimate_no, estimate_date, accident_date, customer, shop, damage_part_text, damage_position,
       items_json, items_sum, subtotal, tax, total,
       NOT (coalesce(items_sum = subtotal AND subtotal + tax = total, false)) AS needs_review,
       min_confidence, error, current_timestamp() AS processed_at
FROM (
  -- 3. ai_extract の結果（VARIANT）から、項目ごとの値を取り出して列にする
  SELECT case_id, path,
         ex:response:estimate_no:value::STRING      AS estimate_no,
         ex:response:estimate_date:value::STRING    AS estimate_date,
         ex:response:accident_date:value::STRING    AS accident_date,
         ex:response:customer:value::STRING         AS customer,
         ex:response:shop:value::STRING             AS shop,
         ex:response:damage_part_text:value::STRING AS damage_part_text,
         ex:response:damage_position:value::STRING  AS damage_position,
         to_json(ex:response:items)                 AS items_json,
         aggregate(cast(ex:response:items AS ARRAY<VARIANT>), 0L,
                   (acc, i) -> acc + coalesce(i:amount:value::BIGINT, 0)) AS items_sum,   -- 明細の金額の合計
         ex:response:subtotal:value::BIGINT AS subtotal,
         ex:response:tax:value::BIGINT      AS tax,
         ex:response:total:value::BIGINT    AS total,
         {min_conf} AS min_confidence,
         ex:error_message::STRING AS error
  FROM (
    -- 2. 文書を読み（ai_parse_document）、項目を取り出す（ai_extract）
    SELECT b.case_id, b.path,
           ai_extract(ai_parse_document(b.content), '{EXTRACT_SCHEMA}',
                      map('version', '2.1', 'enableConfidenceScores', 'true')) AS ex
    -- 1. Bronze の見積書のうち、Silver にまだ無いもの（未処理）だけを選ぶ
    FROM {BRONZE} b LEFT ANTI JOIN {SILVER_FORM} s ON b.path = s.path
    WHERE b.modality = 'form'
  )
)"""
display(spark.sql(sql))   # num_inserted_rows：今回処理した見積書の件数

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確かめる：信頼度と検算
# MAGIC
# MAGIC - `min_confidence` は、`ai_extract` が項目ごとに返す信頼度（0〜1）のうち、いちばん低い値です。
# MAGIC - `needs_review` は、計算の検算が合わなかった見積書です。
# MAGIC
# MAGIC 手書きの見積書（case_05）の行を見てください。見積書に書かれた小計（118,000円）が、明細の合計（117,000円）と合いません。書いた人の計算の誤りで、`ai_extract` は書かれた値を正しく読んでいます。そのため、信頼度を見ても、この誤りには気づけません。`needs_review` は検算で true になります。
# MAGIC
# MAGIC **信頼度は、取り出した値が正しいかどうかの保証にはなりません。** 信頼度は実行のたびに揺れ、正しく読めた項目で低く出ることもあります。人が確認する見積書は、業務のルール（ここでは計算の検算）で振り分けます。

# COMMAND ----------

display(spark.sql(f"""
SELECT case_id, shop, items_sum, subtotal, tax, total, min_confidence, needs_review
FROM {SILVER_FORM} ORDER BY case_id"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver テーブルの中身
# MAGIC
# MAGIC 見積書1件が1行です。和暦の日付（case_05 の「R8.10.27」）が西暦の `2026-10-27` に直っていることも確かめてください。

# COMMAND ----------

display(spark.table(SILVER_FORM).orderBy("case_id"))
