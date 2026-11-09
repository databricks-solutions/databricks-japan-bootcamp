# Databricks notebook source
# MAGIC %md
# MAGIC # 03 Silver｜写真から取り出す
# MAGIC
# MAGIC **型のどこか**：取り込む → **AI で取り出す** → 確かめる → つなぐ
# MAGIC
# MAGIC 損害写真から、損傷の位置・部位・種類・程度を取り出します。02 と違い、**SQL だけで書けます**。
# MAGIC
# MAGIC | | この工程 |
# MAGIC |---|---|
# MAGIC | 手段 | [`ai_query`](https://docs.databricks.com/aws/ja/sql/language-manual/functions/ai_query)（`files => content` で画像を渡し、`responseFormat` で JSON スキーマを指定） |
# MAGIC | なぜこの手段か | 画像は `ai_query` に直接渡せる。JSON スキーマの列挙値で、答えを決めた選択肢に限定できる |
# MAGIC | 課金 | 呼び出すモデルが **バッチ推論の対応モデル** のときは、バッチ推論として時間課金（使った処理能力 × 時間）。対応モデルでなければトークン課金。ここで使う Gemini 3.5 Flash は対応モデル（[ai_query によるバッチ推論](https://docs.databricks.com/aws/ja/large-language-models/ai-query)） |
# MAGIC
# MAGIC 注意：`responseFormat`（JSON スキーマの指定）に対応しないモデルもあります。モデルを替えるときは、[構造化出力](https://docs.databricks.com/aws/ja/machine-learning/model-serving/structured-outputs) の対応状況を確かめてください。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 写真を見てみる
# MAGIC
# MAGIC Bronze に取り込んだ写真を3枚表示します。どの写真も、車の向き（前後・左右）が分かる構図です。

# COMMAND ----------

import base64

rows = spark.table(BRONZE).filter("modality = 'image'").orderBy("case_id").select("case_id", "content").limit(3).collect()
displayHTML("".join(
    f'<figure style="display:inline-block;margin:4px"><img src="data:image/jpeg;base64,{base64.b64encode(r.content).decode()}" width="320">'
    f'<figcaption>{r.case_id}</figcaption></figure>' for r in rows))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 未処理の写真だけを処理して Silver に追記する
# MAGIC
# MAGIC 1つの SQL で、次の3つを内側から順に行います。
# MAGIC
# MAGIC 1. **未処理の写真を選ぶ**：Bronze の写真のうち、Silver に同じ `path` の行が無いもの（`LEFT ANTI JOIN`）
# MAGIC 2. **`ai_query` でモデルに渡す**：
# MAGIC    - 第1引数：モデル名
# MAGIC    - 第2引数：指示文
# MAGIC    - `files => b.content`：画像ファイルの中身（Bronze の `content` 列をそのまま渡す）
# MAGIC    - `responseFormat`：返す JSON の形。`enum` で選択肢を決める（02・04 と同じ選択肢）
# MAGIC    - `failOnError => false`：1件失敗しても全体を止めず、結果を `result`（答え）と `errorMessage`（エラー）の組で返す
# MAGIC 3. **列に分けて追記する**：答えの JSON を `from_json` で列に分け、Silver に `INSERT INTO` する
# MAGIC
# MAGIC 出力の `num_inserted_rows` が、今回モデルに渡した写真の件数です。1回目は5件、もう一度実行すると0件になります。

# COMMAND ----------

import json

PROMPT = ("この自動車の損害写真を見て、損傷の位置・部位・種類・程度を答えてください。"
          "左右は車の進行方向（運転席に座って前を向いたとき）を基準にしてください。")

# 返す JSON の形（strict：スキーマどおりの JSON だけを返させる）
RESPONSE_FORMAT = json.dumps({"type": "json_schema", "json_schema": {"name": "damage", "strict": True, "schema": {
    "type": "object",
    "properties": {
        "damage_position": {"type": "string", "enum": DAMAGE_POSITIONS},
        "damage_part": {"type": "string", "enum": DAMAGE_PARTS},
        "damage_type": {"type": "string", "enum": ["すり傷", "へこみ", "割れ", "ひび"]},
        "severity": {"type": "string", "enum": SEVERITIES},
    },
    "required": ["damage_position", "damage_part", "damage_type", "severity"],
    "additionalProperties": False}}}, ensure_ascii=False)

# Silver テーブルを用意する（初回だけ作られる）
spark.sql(f"""CREATE TABLE IF NOT EXISTS {SILVER_IMAGE} (
  case_id STRING, path STRING,
  damage_position STRING, damage_part STRING, damage_type STRING, severity STRING,
  raw_json STRING, error STRING, processed_at TIMESTAMP)""")

sql = f"""
INSERT INTO {SILVER_IMAGE}
-- 3. 答えの JSON を列に分けて、Silver に追記する
SELECT case_id, path,
       j.damage_position, j.damage_part, j.damage_type, j.severity,
       r.result AS raw_json, r.errorMessage AS error, current_timestamp() AS processed_at
FROM (
  SELECT case_id, path, r,
         from_json(r.result, 'damage_position STRING, damage_part STRING, damage_type STRING, severity STRING') AS j
  FROM (
    -- 2. ai_query で写真をモデルに渡す
    SELECT b.case_id, b.path,
           ai_query('{IMAGE_MODEL}', '{PROMPT}',
                    files => b.content,
                    responseFormat => '{RESPONSE_FORMAT}',
                    failOnError => false) AS r
    -- 1. Bronze の写真のうち、Silver にまだ無いもの（未処理）だけを選ぶ
    FROM {BRONZE} b LEFT ANTI JOIN {SILVER_IMAGE} s ON b.path = s.path
    WHERE b.modality = 'image'
  )
)"""
display(spark.sql(sql))   # num_inserted_rows：今回モデルに渡した写真の件数

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver テーブルの中身
# MAGIC
# MAGIC 写真1枚が1行になり、損傷の位置・部位・種類・程度が列に分かれています。上で表示した写真と見比べてみてください。

# COMMAND ----------

display(spark.table(SILVER_IMAGE).drop("raw_json").orderBy("case_id"))
