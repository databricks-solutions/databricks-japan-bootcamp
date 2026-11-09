# Databricks notebook source
# MAGIC %md
# MAGIC # 05 Gold｜つなぐ
# MAGIC
# MAGIC **型のどこか**：取り込む → AI で取り出す → 確かめる → **つなぐ**
# MAGIC
# MAGIC 音声・写真・見積書の3つの Silver を、受付番号 `case_id` で **事故1件＝1行** のテーブル（Gold）にまとめます。
# MAGIC 1つの形式だけを見ていては分からない **食い違い** が、つなぐと見つかります。たとえば次のようなものです。
# MAGIC
# MAGIC - 通話では「左前をこすった」と申告しているのに、写真と見積書では右後ろが損傷している
# MAGIC - 通話では「ほんの少しこすっただけ」と申告しているのに、見積が高額
# MAGIC
# MAGIC この工程は LLM を呼ばず、SQL の結合と条件式だけで作ります。費用がほとんどかからないため、Silver のような増分処理にはせず、毎回 Silver 全体から作り直します。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 食い違いの定義（業務のルール）
# MAGIC
# MAGIC どういう状態を「確認が必要な食い違い」とみなすかは、業務で決めるルールです。ここでは次の3つにします。
# MAGIC
# MAGIC | 食い違い | 定義 |
# MAGIC |---|---|
# MAGIC | 損傷位置の食い違い | 通話での申告・写真・見積書のあいだで、損傷の位置（左前・右後ろ など）が一致しない |
# MAGIC | 申告の程度と金額の食い違い | 通話で「軽微」と申告しているのに、見積の合計が `HIGH_AMOUNT` 円以上 |
# MAGIC | 見積書の検算エラー | 04 の検算が合わなかった（`needs_review`） |
# MAGIC
# MAGIC 損傷の位置は、02・03・04 で同じ選択肢（`DAMAGE_POSITIONS`）から取り出しているので、そのまま比べられます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold テーブルを作る
# MAGIC
# MAGIC 1. **案件の一覧**：Bronze から受付番号の一覧を作り、そこに3つの Silver を `LEFT JOIN` でつなぎます。どれかの形式が欠けていても、案件の行は残ります。
# MAGIC 2. **列の名前**：同じ「損傷の位置」でも出どころが違うので、`said_`（通話での申告）・`photo_`（写真）・`estimate_`（見積書）を頭に付けて区別します。
# MAGIC 3. **食い違いの判定**：上の3つの定義を `CASE WHEN` で書き、当てはまったものだけを `findings`（配列）に入れます。
# MAGIC    - 損傷位置：3つの位置から NULL を除き、重複を除いた件数（`array_distinct`）が2以上なら、どこかが一致していない

# COMMAND ----------

HIGH_AMOUNT = 200_000   # 軽微な損傷にしては高額とみなす見積額（円）。業務に合わせて決める

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD} AS
SELECT
  c.case_id,
  -- 通話での申告（02）
  a.accident_datetime, a.situation, a.summary,
  a.damage_position AS said_position,  a.damage_part AS said_part,  a.damage_severity AS said_severity,
  -- 写真（03）
  i.damage_position AS photo_position, i.damage_part AS photo_part, i.severity AS photo_severity,
  -- 見積書（04）
  f.damage_position AS estimate_position, f.damage_part_text AS estimate_part, f.shop, f.total, f.needs_review,
  -- 食い違いの判定：当てはまったものだけを配列に残す
  filter(array(
    CASE WHEN size(array_distinct(filter(array(a.damage_position, i.damage_position, f.damage_position), x -> x IS NOT NULL))) > 1
         THEN '損傷位置の食い違い' END,
    CASE WHEN a.damage_severity = '軽微' AND f.total >= {HIGH_AMOUNT}
         THEN '申告の程度と金額の食い違い' END,
    CASE WHEN f.needs_review THEN '見積書の検算エラー' END
  ), x -> x IS NOT NULL) AS findings
FROM (SELECT DISTINCT case_id FROM {BRONZE}) c      -- 1. 案件の一覧
LEFT JOIN {SILVER_AUDIO} a USING (case_id)
LEFT JOIN {SILVER_IMAGE} i USING (case_id)
LEFT JOIN {SILVER_FORM}  f USING (case_id)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 事故1件＝1行のテーブル
# MAGIC
# MAGIC 損傷の位置を、申告・写真・見積書の順に並べています。行ごとに見比べると、`findings` に入った食い違いの理由が分かります。

# COMMAND ----------

display(spark.sql(f"""
SELECT case_id, said_position, photo_position, estimate_position,
       said_severity, photo_severity, total, needs_review, findings
FROM {GOLD} ORDER BY case_id"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認が必要な案件
# MAGIC
# MAGIC `findings` が空でない案件だけを、通話の要点（`summary`）と一緒に表示します。担当者が最初に見るべき一覧です。

# COMMAND ----------

display(spark.sql(f"""
SELECT case_id, findings, summary, said_position, photo_position, estimate_position, said_severity, total
FROM {GOLD} WHERE size(findings) > 0 ORDER BY case_id"""))
