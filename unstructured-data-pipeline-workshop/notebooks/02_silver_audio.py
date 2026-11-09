# Databricks notebook source
# MAGIC %md
# MAGIC # 02 Silver｜音声から取り出す
# MAGIC
# MAGIC **型のどこか**：取り込む → **AI で取り出す** → 確かめる → つなぐ
# MAGIC
# MAGIC 事故受付の通話音声を、**文字起こしの工程を挟まずに** 基盤モデル（Gemini）へ直接入力し、事故の状況と契約者の申告内容を JSON で受け取ります。受け取った JSON を列に分けて、Silver テーブルに追記します。
# MAGIC
# MAGIC | | この工程 |
# MAGIC |---|---|
# MAGIC | 手段 | 基盤モデル API を Python から呼ぶ（OpenAI 互換のクライアント） |
# MAGIC | なぜこの手段か | SQL の `ai_query` に渡せるファイルは画像（JPEG/PNG）だけで、音声は渡せない。音声を入力できるモデルを API で呼ぶ |
# MAGIC | 課金 | トークン課金（入力・出力のトークン数 × 単価） |
# MAGIC
# MAGIC ### 増分処理
# MAGIC
# MAGIC Bronze の音声のうち、**Silver にまだ無いもの（未処理）だけ** をモデルに渡します。何度実行しても、処理済みの音声をモデルに渡し直すことはなく、もう一度課金されません。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 準備
# MAGIC
# MAGIC 基盤モデル API を呼ぶための `openai` ライブラリを入れ、Python を再起動してから共通設定を読み込みます。

# COMMAND ----------

# MAGIC %pip install -q openai

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1件聞いてみる
# MAGIC
# MAGIC Bronze に取り込んだ音声を1件再生します。オペレーターと契約者の会話です（音声は合成音声です）。

# COMMAND ----------

import base64

sample = spark.table(BRONZE).filter("modality = 'audio'").orderBy("case_id").first()
displayHTML(f'<p>{sample.case_id}</p><audio controls src="data:audio/wav;base64,{base64.b64encode(sample.content).decode()}"></audio>')

# COMMAND ----------

# MAGIC %md
# MAGIC ## 音声を入力して、JSON で受け取る関数を作る
# MAGIC
# MAGIC - **クライアント**：Databricks の基盤モデルは OpenAI 互換の API で呼べます。接続先（`/serving-endpoints`）とトークンは、このノートブックの実行情報から取ります。
# MAGIC - **指示文（`PROMPT`）**：何を取り出すかを日本語で書きます。損傷の位置の左右は、写真・見積書と同じ基準（車の進行方向）にそろえます。
# MAGIC - **JSON スキーマ（`AUDIO_SCHEMA`）**：返してほしい項目と型を指定します。`enum` を付けた項目は、決めた選択肢の中からしか答えが返りません。損傷の位置・部位・程度は、03（写真）・04（見積書）と同じ選択肢にし、05 で突き合わせられるようにします。
# MAGIC - **音声の渡し方**：音声ファイルを base64 の文字列にして、`audio_url` として指示文と一緒に送ります。

# COMMAND ----------

import json
from openai import OpenAI

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
client = OpenAI(api_key=ctx.apiToken().get(), base_url=f"{ctx.apiUrl().get()}/serving-endpoints")

PROMPT = ("この事故受付の通話音声を聞き、契約者の申告内容を取り出してください。"
          "損傷の位置の左右は、車の進行方向（運転席に座って前を向いたとき）を基準にしてください。")

AUDIO_SCHEMA = {
    "type": "object",
    "properties": {
        "accident_datetime": {"type": "string", "description": "事故の日時（通話で述べた表現のまま）"},
        "location": {"type": "string", "description": "事故の場所"},
        "situation": {"type": "string", "description": "事故の状況を1文で"},
        "injury": {"type": "string", "description": "けがの有無と内容"},
        "counterparty": {"type": "string", "enum": ["あり", "なし", "不明"], "description": "相手の有無"},
        "damage_position": {"type": "string", "enum": DAMAGE_POSITIONS, "description": "契約者が申告した損傷の位置"},
        "damage_part": {"type": "string", "enum": DAMAGE_PARTS, "description": "契約者が申告した損傷の部位"},
        "damage_severity": {"type": "string", "enum": SEVERITIES, "description": "契約者が申告した損傷の程度"},
        "repair_shop": {"type": "string", "description": "修理を依頼する工場の名前"},
        "summary": {"type": "string", "description": "通話の要点を1〜2文で"},
    },
    "required": ["accident_datetime", "location", "situation", "injury", "counterparty",
                 "damage_position", "damage_part", "damage_severity", "repair_shop", "summary"],
    "additionalProperties": False,
}

def analyze_audio(content: bytes) -> str:
    """音声ファイルの中身を Gemini に渡し、AUDIO_SCHEMA の形の JSON 文字列を返す"""
    resp = client.chat.completions.create(
        model=AUDIO_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64," + base64.b64encode(content).decode()}},
        ]}],
        # 返す JSON の形を指定する（strict：スキーマどおりの JSON だけを返させる）
        response_format={"type": "json_schema", "json_schema": {"name": "accident_call", "schema": AUDIO_SCHEMA, "strict": True}},
    )
    c = resp.choices[0].message.content
    # モデルによっては本文が「パーツの配列」で返るため、文字列の部分だけをつなぐ
    return c if isinstance(c, str) else "".join(p.get("text", "") for p in c if isinstance(p, dict))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1件で試す
# MAGIC
# MAGIC 上で再生した音声を関数に渡し、返ってきた JSON を表示します。音声の中で話された内容が、項目ごとに分かれて返ることを確かめてください。
# MAGIC
# MAGIC このセルは初回だけモデルを呼びます。2回目以降（06 で 01〜05 をもう一度実行するときなど）は、処理済みの音声に課金しないよう呼び出しを省きます。

# COMMAND ----------

if not spark.catalog.tableExists(SILVER_AUDIO):
    print(json.dumps(json.loads(analyze_audio(sample.content)), ensure_ascii=False, indent=2))
else:
    print("2回目以降の実行なので、試しの呼び出しは省きます")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 未処理の音声だけを処理して Silver に追記する
# MAGIC
# MAGIC 1. **Silver テーブルを用意する**：初回だけ作ります（`CREATE TABLE IF NOT EXISTS`）。
# MAGIC 2. **未処理の音声を選ぶ**：Bronze の音声のうち、Silver に同じ `path` の行が無いものを選びます。`LEFT ANTI JOIN` は「右のテーブルに一致する行が無い、左のテーブルの行」だけを返す結合です。
# MAGIC 3. **モデルに渡す**：選んだ音声を、4件ずつ並行して関数に渡します。1件失敗しても全体は止めず、エラーの内容を `error` 列に残します。
# MAGIC 4. **列に分けて追記する**：返ってきた JSON を `from_json` で列に分け、処理した時刻（`processed_at`）を付けて Silver に追記します。
# MAGIC
# MAGIC 出力の「未処理の音声」と「今回モデルに渡した音声」の件数を見てください。1回目は5件、もう一度実行すると0件になります。

# COMMAND ----------

from concurrent.futures import ThreadPoolExecutor
from pyspark.sql import functions as F

# 1. Silver テーブルを用意する（初回だけ作られる）
spark.sql(f"""CREATE TABLE IF NOT EXISTS {SILVER_AUDIO} (
  case_id STRING, path STRING,
  accident_datetime STRING, location STRING, situation STRING, injury STRING, counterparty STRING,
  damage_position STRING, damage_part STRING, damage_severity STRING, repair_shop STRING, summary STRING,
  raw_json STRING, error STRING, processed_at TIMESTAMP)""")

# 2. Bronze の音声のうち、Silver にまだ無いもの（未処理）だけを選ぶ
new_audio = spark.sql(f"""
SELECT b.case_id, b.path, b.content
FROM {BRONZE} b LEFT ANTI JOIN {SILVER_AUDIO} s ON b.path = s.path
WHERE b.modality = 'audio'""").collect()
print("未処理の音声:", [r.case_id for r in new_audio])

# 3. モデルに渡す（4件ずつ並行。失敗した音声はエラーの内容を残す）
def run(row):
    try:
        return (row.case_id, row.path, analyze_audio(bytes(row.content)), None)
    except Exception as e:
        return (row.case_id, row.path, None, str(e)[:500])

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(run, new_audio))

# 4. 返ってきた JSON を列に分けて、Silver に追記する
if results:
    fields = list(AUDIO_SCHEMA["properties"])
    df = spark.createDataFrame(results, "case_id string, path string, raw_json string, error string")
    parsed = F.from_json("raw_json", ", ".join(f"{f} STRING" for f in fields))   # JSON 文字列 → 項目ごとの列
    (df.select("case_id", "path", *[parsed[f].alias(f) for f in fields], "raw_json", "error",
               F.current_timestamp().alias("processed_at"))
       .write.mode("append").saveAsTable(SILVER_AUDIO))
print("今回モデルに渡した音声:", len(results), "件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver テーブルの中身
# MAGIC
# MAGIC 通話1件が1行になり、申告内容が列に分かれています。`error` 列が空なら、すべて正しく処理できています。

# COMMAND ----------

display(spark.table(SILVER_AUDIO).drop("raw_json").orderBy("case_id"))
