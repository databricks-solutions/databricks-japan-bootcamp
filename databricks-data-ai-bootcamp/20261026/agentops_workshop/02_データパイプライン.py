# Databricks notebook source
# MAGIC %md
# MAGIC # 02. データパイプライン: 文書と過去の対応を、エージェントが使える形にする（約12分）
# MAGIC
# MAGIC | # | 処理 | 使う機能 | できるもの |
# MAGIC |---|---|---|---|
# MAGIC | 1 | PDF をパースする | `ai_parse_document` | 本文・見出し・表の構造化データ |
# MAGIC | 2 | 検索用のチャンクに分け、型番を付ける | `ai_prep_search` | `doc_chunks` |
# MAGIC | 3 | 過去の対応メモの個人情報をマスクする | `ai_mask` | `past_cases` |
# MAGIC | 4 | 検索インデックスを作る | AI Search（埋め込みは自動） | `doc_chunks_index` / `past_cases_index` |
# MAGIC | 5 | 製品情報を調べる関数を作る | UC関数 | `get_product_info`（エージェントのツールになる） |
# MAGIC
# MAGIC 使うデータ（PDF・テーブル）は、`01_準備` で Volume とテーブルに置いてあります。データからエージェントのツールまで、すべて Unity Catalog で管理されます。

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. `ai_parse_document` で PDF をパースする
# MAGIC PDF の本文・見出し・**表**を、構造を保ったまま取り出します。

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE docs_parsed COMMENT 'PDFをai_parse_documentでパースした結果' AS
SELECT path, ai_parse_document(content) AS parsed
FROM read_files('{VOL}/docs/{{manuals,service_bulletins,policies}}/*.pdf', format => 'binaryFile')
""")
display(spark.sql("SELECT path, parsed FROM docs_parsed LIMIT 3"))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. `ai_prep_search` で検索用のチャンクに分け、型番を付ける
# MAGIC パースした結果を、検索に向いた大きさのチャンクに分けます。段階を追って見ていきます（2-1〜2-3 は、取扱説明書 RC-550 の1本だけで試します）。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2-1. 素の結果を見る
# MAGIC `ai_prep_search` に、パースした結果をそのまま渡します。戻り値は VARIANT（JSON）で、`document.contents` の下にチャンクが並びます。

# COMMAND ----------

display(spark.sql("SELECT ai_prep_search(parsed) AS prepped FROM docs_parsed WHERE path LIKE '%manual_RC-550%'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2-2. チャンクに展開する
# MAGIC 1行1チャンクに展開します。チャンクごとに、2種類の本文があります。
# MAGIC - `chunk_to_retrieve`: エージェントに渡す本文
# MAGIC - `chunk_to_embed`: 埋め込み（検索）に使う本文。先頭に、文書から読み取った情報（製品の型番など）や見出しの一覧が自動で付くので、チャンク単体でも何の文書かがわかる

# COMMAND ----------

display(spark.sql("""
  SELECT c.value:chunk_position::INT AS chunk_position,
         c.value:chunk_to_embed::STRING AS chunk_to_embed,
         c.value:chunk_to_retrieve::STRING AS chunk_to_retrieve
  FROM (SELECT ai_prep_search(parsed) AS prepped FROM docs_parsed WHERE path LIKE '%manual_RC-550%'),
       LATERAL variant_explode(prepped:document:contents) AS c"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2-3. `schema` オプションで、型番を取り出す
# MAGIC `schema` に取り出したい項目（型番 `model_no` と文書の種類 `document_type`）を指定すると、チャンクごとに `metadata` として返ります。
# MAGIC 炊飯器 RC-500 と上位機種 RC-550 の取扱説明書は文面がほぼ同じで、ベクトル検索だけでは区別できません。型番を項目として持たせておくと、検索で絞り込めます。

# COMMAND ----------

display(spark.sql("""
  SELECT c.value:chunk_position::INT AS chunk_position,
         c.value:metadata AS metadata,
         left(c.value:chunk_to_retrieve::STRING, 200) AS chunk_to_retrieve
  FROM (SELECT ai_prep_search(parsed, map('schema', '["model_no", "document_type"]')) AS prepped
        FROM docs_parsed WHERE path LIKE '%manual_RC-550%'),
       LATERAL variant_explode(prepped:document:contents) AS c"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2-4. すべての文書をチャンクにし、型番を列に取り出す
# MAGIC `metadata` の型番と文書の種類を、それぞれ列（`model_no`・`doc_type`）に取り出してテーブルにします。特定の型番がない文書（保証規定など）は、全製品共通として `ALL` にします。
# MAGIC （テーブルは初回だけ作り、再実行時は中身を上書きします。検索インデックスとの同期を保つためです）

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS doc_chunks (
  chunk_id STRING COMMENT 'チャンクID',
  source_file STRING COMMENT '元のファイル名',
  doc_type STRING COMMENT '文書の種類（取扱説明書・サービス技術情報・保証規定）',
  model_no STRING COMMENT '対象の型番。全製品共通の文書は ALL',
  chunk_text STRING COMMENT 'エージェントに渡す本文',
  chunk_to_embed STRING COMMENT '埋め込みに使う本文（文書の文脈付き）')
COMMENT '検索用に分割した文書のチャンク'
TBLPROPERTIES (delta.enableChangeDataFeed = true)""")

spark.sql("""
INSERT OVERWRITE doc_chunks
WITH prepped AS (
  SELECT regexp_extract(path, '([^/]+)$', 1) AS source_file,
         ai_prep_search(parsed, map('schema', '["model_no", "document_type"]')) AS prepped
  FROM docs_parsed)
SELECT concat(source_file, '#', c.value:chunk_position::INT) AS chunk_id,
       source_file,
       coalesce(c.value:metadata:document_type::STRING, '保証規定') AS doc_type,
       coalesce(c.value:metadata:model_no::STRING, 'ALL') AS model_no,
       c.value:chunk_to_retrieve::STRING AS chunk_text,
       c.value:chunk_to_embed::STRING AS chunk_to_embed
FROM prepped, LATERAL variant_explode(prepped:document:contents) AS c""")

display(spark.sql("SELECT source_file, doc_type, model_no, count(*) AS chunks FROM doc_chunks GROUP BY ALL ORDER BY doc_type, source_file"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2-5. 型番が正しく取り出せたかを確かめる
# MAGIC 取扱説明書は、ファイル名の型番（`manual_RC-550.pdf` → `RC-550`）と一致するはずです。

# COMMAND ----------

display(spark.sql("""
  SELECT source_file, model_no,
         model_no = regexp_extract(source_file, 'manual_([A-Z]{2}-[0-9]{3})', 1) AS matches_file_name
  FROM doc_chunks WHERE source_file LIKE 'manual_%' GROUP BY ALL ORDER BY source_file"""))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `ai_mask` で対応メモの個人情報をマスクする
# MAGIC 過去の対応メモには、お客様の氏名・電話番号・住所が書かれています。エージェントの検索対象にする前に、マスクします。

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS past_cases (
  request_id STRING COMMENT '受付ID',
  model_no STRING COMMENT '型番',
  symptom_category STRING COMMENT '症状の区分',
  result_category STRING COMMENT '対応結果',
  case_text STRING COMMENT '個人情報をマスクした事例の本文')
COMMENT '個人情報をマスクした過去の対応事例'
TBLPROPERTIES (delta.enableChangeDataFeed = true)""")

spark.sql("""
INSERT OVERWRITE past_cases
WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY model_no, symptom_category, result_category ORDER BY received_at DESC) AS rn
  FROM repair_requests WHERE received_at >= '2026-01-01')
SELECT request_id, model_no, symptom_category, result_category,
       concat('型番: ', model_no, ' / 症状: ', symptom_category, ' / 対応結果: ', result_category, ' / 対応メモ: ',
              ai_mask(operator_memo, array('person', 'phone', 'email', 'address'))) AS case_text
FROM ranked WHERE rn <= 5""")

display(spark.sql("SELECT count(*) AS cases FROM past_cases"))
display(spark.sql("SELECT * FROM past_cases LIMIT 10"))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 検索インデックスを作る
# MAGIC 共有の AI Search のエンドポイント（`00_設定` の `VS_ENDPOINT`。`01_準備` で作成）に、自分のインデックスを2つ作ります。埋め込みは AI Search が自動で計算し、元のテーブルと同期します（Delta Sync）。
# MAGIC
# MAGIC | インデックス | 元のテーブル | 作り方 |
# MAGIC |---|---|---|
# MAGIC | `past_cases_index` | `past_cases`（マスクした過去事例） | 4-1. コードで作る |
# MAGIC | `doc_chunks_index` | `doc_chunks`（文書のチャンク） | 4-2. 画面（UI）で作る |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4-1. コードで作る（過去事例）
# MAGIC Databricks SDK で作ります。作成を始めるだけで、完了は待ちません（同期のあいだに 4-2 を進めます）。

# COMMAND ----------

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.vectorsearch import (DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn, PipelineType,
                                                 VectorIndexType)

w = WorkspaceClient()


def query_with_retry(index, **kwargs):
    """検索する。インデックスの準備がまだなら（作った直後や作り直した直後）、少し待ってから呼び直す。"""
    for attempt in range(40):
        try:
            return w.vector_search_indexes.query_index(index, **kwargs)
        except Exception as e:
            if "not ready" not in str(e) or attempt == 39:
                raise
            time.sleep(15)


INDEXES = {   # インデックス → 元のテーブル・主キー・埋め込みの元の列
    DOC_INDEX: dict(source=f"{S}.doc_chunks", pk="chunk_id", col="chunk_to_embed"),
    CASE_INDEX: dict(source=f"{S}.past_cases", pk="request_id", col="case_text"),
}


def create_or_sync(name):
    cfg = INDEXES[name]
    try:
        w.vector_search_indexes.get_index(name)
        w.vector_search_indexes.sync_index(name)          # すでにあれば同期だけ
        print(f"{name}: 作成済みなので、同期しました")
    except NotFound:
        w.vector_search_indexes.create_index(
            name=name, endpoint_name=VS_ENDPOINT, primary_key=cfg["pk"], index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=cfg["source"], pipeline_type=PipelineType.TRIGGERED,
                embedding_source_columns=[EmbeddingSourceColumn(name=cfg["col"], embedding_model_endpoint_name=EMBEDDING_ENDPOINT)]))
        print(f"{name}: 作成を始めました")


create_or_sync(CASE_INDEX)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4-2. 画面（UI）で作る（文書）
# MAGIC 次のセルを実行して表示されるリンクから `doc_chunks` テーブルを開き、右上の **Create → Vector search index** を選んで、表の値を入れます（表にない項目は既定のまま）。

# COMMAND ----------

displayHTML(f"""
<p><a href="/explore/data/{CATALOG}/{SCHEMA}/doc_chunks" target="_blank">doc_chunks テーブルを開く</a>（右上の <b>Create → Vector search index</b>）</p>
<table border="1" cellpadding="6" style="border-collapse: collapse">
<tr><th>項目</th><th>入れる値</th></tr>
<tr><td>Name</td><td><code>{DOC_INDEX}</code></td></tr>
<tr><td>Index type</td><td>既定のまま</td></tr>
<tr><td>Primary key</td><td><code>chunk_id</code></td></tr>
<tr><td>Embedding source</td><td>Compute embeddings（列は <code>chunk_to_embed</code>）</td></tr>
<tr><td>Advanced settings → Embedding model</td><td><code>{EMBEDDING_ENDPOINT}</code>（日本語に対応したモデル。既定のモデルから変える）</td></tr>
<tr><td>Save computed embeddings</td><td>オフのまま</td></tr>
<tr><td>Vector Search endpoint</td><td><code>{VS_ENDPOINT}</code></td></tr>
<tr><td>Sync mode</td><td>Triggered</td></tr>
</table>
<p>作れたら、インデックスの画面で状態が「Online」になるのを確かめます（数分）。</p>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4-3. 2つのインデックスの準備ができるのを待つ
# MAGIC 画面での作成がうまくいかなかった場合は、`CREATE_DOC_INDEX_BY_CODE` を `True` にして実行すると、同じ設定でコードから作ります。

# COMMAND ----------

CREATE_DOC_INDEX_BY_CODE = False   # True にすると、doc_chunks_index をコードで作る（画面で作れなかった場合）

if CREATE_DOC_INDEX_BY_CODE:
    create_or_sync(DOC_INDEX)
for name, cfg in INDEXES.items():
    try:
        w.vector_search_indexes.get_index(name)
    except NotFound:
        raise RuntimeError(f"{name} がまだありません。4-2 の手順で画面から作るか、CREATE_DOC_INDEX_BY_CODE を True にしてください")
    rows = spark.table(cfg["source"]).count()   # 元のテーブルの行がすべて入るまで待つ
    for _ in range(120):
        st = w.vector_search_indexes.get_index(name).status
        if st.ready and (st.indexed_row_count or 0) >= rows:
            break
        time.sleep(30)
    query_with_retry(name, columns=[cfg["pk"]], query_text="テスト", num_results=1)   # 実際に検索できるまで待つ
    print(name, "ready" if st.ready else "準備中", st.indexed_row_count, "/", rows)


# COMMAND ----------

# MAGIC %md
# MAGIC 型番で絞り込む意味を確かめます。RC-550 で「E-21」は「圧力弁の詰まり」、RC-500 では「温度センサーの異常」で、意味がまったく違います。

# COMMAND ----------

import json

COLS = ["chunk_id", "model_no", "chunk_text"]

def search(filters=None):
    res = query_with_retry(DOC_INDEX, columns=COLS, query_text="E-21が表示されて炊飯できない", num_results=5,
                           filters_json=json.dumps(filters) if filters else None)
    for row in res.result.data_array:
        print(f"[{row[1]}] {row[0]}  score={float(row[-1]):.3f}\n   {row[2][:120].replace(chr(10), ' ')}")

print("=== 絞り込みなし ===")
search()
print("\n=== 型番 RC-550 で絞り込み ===")
search({"model_no": ["RC-550", "ALL"]})


# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 製品情報を調べる UC関数を作る
# MAGIC 製造番号から、型番・ロット・製造月・保証の状態を調べる関数です。エージェントは、この関数を MCP 経由でツールとして使います。

# COMMAND ----------

# デプロイしたアプリに付いた実行権限を消さないよう、作り直さない（CREATE OR REPLACE にすると権限が消える）
spark.sql(f"""
CREATE FUNCTION IF NOT EXISTS {S}.get_product_info(
  serial_no STRING COMMENT '製造番号（例: RC5-2604B-00871）',
  purchase_date STRING COMMENT '購入日（YYYY-MM-DD）。わからない場合は空文字')
RETURNS TABLE (model_no STRING, product_name STRING, lot_no STRING, production_month STRING, factory STRING, warranty_status STRING)
COMMENT '製造番号から、型番・製品名・ロット番号・製造月・製造工場・保証の状態を調べる。該当がなければ0行'
RETURN
  SELECT l.model_no, p.product_name, l.lot_no, date_format(l.production_month, 'yyyy-MM') AS production_month, l.factory,
         CASE WHEN purchase_date IS NULL OR purchase_date = '' THEN '購入日不明'
              WHEN add_months(to_date(purchase_date), p.warranty_months) >= current_date() THEN '保証期間内'
              ELSE '保証期間外' END AS warranty_status
  FROM {S}.production_lots l JOIN {S}.products p ON l.model_no = p.model_no
  WHERE l.lot_no = regexp_extract(serial_no, '^([A-Z0-9]{{3}}-[0-9]{{4}}[A-C])', 1)
""")
display(spark.sql(f"SELECT * FROM {S}.get_product_info('RC6-2509A-00321', '2025-10-05')"))


# COMMAND ----------

# MAGIC %md
# MAGIC → `03_エージェント` で、これらをツールとして使うエージェントを動かします。
