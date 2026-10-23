# Databricks notebook source
# MAGIC %md
# MAGIC # 01. 準備: 使うリソースとデータを用意する（約5分）
# MAGIC
# MAGIC **ハンズオンの最初に実行します。** `00_設定` の `CATALOG` を書き換えてから、このノートブックを上から実行してください。AI Search の立ち上げ（初回は約20分）は、このあとの説明を聞いているあいだに進みます。何度実行しても問題ありません。
# MAGIC
# MAGIC | # | やること | 補足 |
# MAGIC |---|---|---|
# MAGIC | 1 | AI Search のエンドポイントを用意し、立ち上げを始める | 参加者で共有する。なければ作る。立ち上げには時間がかかるので、完了は待たずに先へ進む |
# MAGIC | 2 | 使うデータ（PDF・CSV）を Volume に置き、テーブルを作る | このフォルダの `source/` から |
# MAGIC | 3 | モデル・AI関数・SQL ウェアハウスが使えるかを確かめる | 最後の表がすべて「OK」なら準備完了 |

# COMMAND ----------

# MAGIC %run ./00_設定

# COMMAND ----------

import time

import pandas as pd
from databricks.sdk.errors import NotFound, ResourceAlreadyExists
from databricks.sdk.service.vectorsearch import (DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn, EndpointType,
                                                 PipelineType, VectorIndexType)

checks = [("カタログ・スキーマ", "OK", S)]   # (項目, 結果, 補足)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. AI Search のエンドポイントを用意し、立ち上げを始める
# MAGIC エンドポイントは参加者で共有します（`00_設定` の `VS_ENDPOINT`）。なければ作ります。
# MAGIC エンドポイントは、最初のインデックスを作ったときに計算資源が立ち上がります（初回は20分ほど）。`02_データパイプライン` で待つ時間を減らすため、小さなダミーのインデックスを作って、立ち上げを先に始めておきます（完了は待ちません）。

# COMMAND ----------


def endpoint_state():
    try:
        return _w.vector_search_endpoints.get_endpoint(VS_ENDPOINT).endpoint_status.state.value
    except NotFound:
        return None


if endpoint_state() is None:
    try:
        _w.vector_search_endpoints.create_endpoint(name=VS_ENDPOINT, endpoint_type=EndpointType.STANDARD)
        print(f"AI Search のエンドポイント {VS_ENDPOINT} を作成しています…（数分）")
    except ResourceAlreadyExists:
        print("ほかの参加者が作成中です。完了を待ちます")
for _ in range(60):
    state = endpoint_state()
    if state in ("ONLINE", "OFFLINE", "PROVISIONING_FAILED", "RED_STATE"):
        break
    time.sleep(20)
try:   # 同じワークスペースのほかの参加者も、このエンドポイントにインデックスを作れるようにする（作った人だけが付けられる）
    _w.api_client.do("PATCH", f"/api/2.0/permissions/vector-search-endpoints/{_w.vector_search_endpoints.get_endpoint(VS_ENDPOINT).id}",
                     body={"access_control_list": [{"group_name": "users", "permission_level": "CAN_USE"}]})
except Exception:
    pass
checks.append(("AI Search のエンドポイント", "OK" if state == "ONLINE" else "NG", f"{VS_ENDPOINT}: {state}"))

# COMMAND ----------

WARMUP_SCHEMA = f"{CATALOG}.workshop_shared"   # 立ち上げ用のダミーのインデックスを置く場所（参加者で共有）
WARMUP_INDEX = f"{WARMUP_SCHEMA}.warmup_index"
try:
    _w.vector_search_indexes.get_index(WARMUP_INDEX)
    checks.append(("AI Search の立ち上げ", "OK", "ダミーのインデックスは作成済み"))
except NotFound:
    try:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {WARMUP_SCHEMA}")
        if not spark.catalog.tableExists(f"{WARMUP_SCHEMA}.warmup_source"):
            spark.sql(f"CREATE TABLE {WARMUP_SCHEMA}.warmup_source TBLPROPERTIES (delta.enableChangeDataFeed = true) AS "
                      "SELECT * FROM VALUES ('1', '取扱説明書'), ('2', '修理受付'), ('3', '無償点検'), ('4', '保証規定'), ('5', '過去事例') AS t(id, text)")
        _w.vector_search_indexes.create_index(
            name=WARMUP_INDEX, endpoint_name=VS_ENDPOINT, primary_key="id", index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=f"{WARMUP_SCHEMA}.warmup_source", pipeline_type=PipelineType.TRIGGERED,
                embedding_source_columns=[EmbeddingSourceColumn(name="text", embedding_model_endpoint_name=EMBEDDING_ENDPOINT)]))
        checks.append(("AI Search の立ち上げ", "OK", "ダミーのインデックスの作成を始めた（完了は待たない）"))
    except Exception as e:
        msg = str(e)
        hint = (f"エンドポイント {VS_ENDPOINT} を使う権限がない。作った人か管理者に CAN USE を付けてもらう"
                if "Can Use" in msg or "PERMISSION" in msg else msg[:150])
        checks.append(("AI Search の立ち上げ", "NG", hint))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 使うデータを置く
# MAGIC このフォルダの `source/` にある PDF（取扱説明書・サービス技術情報・保証規定）と CSV（製品・製造ロット・修理受付）を、Volume とテーブルに置きます。`02_データパイプライン` 以降で使います。

# COMMAND ----------

import os
import shutil

SOURCE = f"{NOTEBOOK_DIR}/source"
COPIES = {  # source/ のフォルダ → Volume のパス
    "tables": f"{VOL}/raw_files/tables",
    "docs": f"{VOL}/docs",
}
for vol in ["raw_files", "docs"]:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {S}.{vol}")

for src, dst in COPIES.items():
    shutil.copytree(f"{SOURCE}/{src}", dst, dirs_exist_ok=True)

for dst in COPIES.values():
    for root, _, files in os.walk(dst):
        for f in sorted(files):
            print(os.path.join(root, f).replace(VOL, ""))


# COMMAND ----------

TABLES = {
    "products": ("製品マスタ。型番ごとの製品名・カテゴリ・発売日・価格・保証期間", [
        ("model_no", "STRING", "型番（例: RC-500）。主キー"),
        ("product_name", "STRING", "製品名"),
        ("category", "STRING", "製品カテゴリ（炊飯器・電気ケトル・電子レンジ・掃除機・空気清浄機・ドライヤー・扇風機・トースター・加湿器）"),
        ("release_date", "DATE", "発売日"),
        ("list_price", "INT", "希望小売価格（円・税込）"),
        ("warranty_months", "INT", "メーカー保証期間（月）")]),
    "production_lots": ("製造ロット。ロット番号ごとの型番・製造工場・製造月・生産台数", [
        ("lot_no", "STRING", "ロット番号（例: RC5-2604B = RC-500 の2026年4月製造のBロット）。製造番号の先頭部分と一致する。主キー"),
        ("model_no", "STRING", "型番。products.model_no と結合"),
        ("factory", "STRING", "製造工場"),
        ("production_month", "DATE", "製造月（月初日）"),
        ("units_produced", "INT", "生産台数")]),
    "repair_requests": ("修理受付の記録。コールセンターが電話・Webで受け付けた修理・問い合わせ1件ごとの症状・対応結果・対応メモ", [
        ("request_id", "STRING", "受付ID。主キー"),
        ("received_at", "TIMESTAMP", "受付日時"),
        ("channel", "STRING", "受付チャネル（電話・Web）"),
        ("model_no", "STRING", "型番。products.model_no と結合"),
        ("serial_no", "STRING", "製造番号（ロット番号-通し番号）"),
        ("lot_no", "STRING", "ロット番号。production_lots.lot_no と結合"),
        ("purchase_date", "DATE", "お客様の購入日"),
        ("symptom_category", "STRING", "症状の区分（電源が入らない・途中で止まる・異音・表示異常 など）"),
        ("result_category", "STRING", "対応結果（出張修理・持込修理・製品交換・修理不要）。修理不要＝使い方やお手入れの案内で解決したもの"),
        ("repair_fee", "INT", "お客様が支払った修理費（円）。保証内は0"),
        ("warranty_status", "STRING", "保証の状態（保証内・保証外）"),
        ("operator_memo", "STRING", "オペレーターの対応メモ（自由記述）。お客様の氏名・電話番号・住所などの個人情報を含む"),
        ("closed_at", "TIMESTAMP", "対応の完了日時")]),
}

for name, (comment, cols) in TABLES.items():
    col_defs = ",\n  ".join(f"{c} {t} COMMENT '{d}'" for c, t, d in cols)
    schema = ", ".join(f"{c} {t}" for c, t, _ in cols)
    spark.sql(f"CREATE OR REPLACE TABLE {S}.{name} (\n  {col_defs}) COMMENT '{comment}'")
    spark.sql(f"""INSERT INTO {S}.{name}
                  SELECT {", ".join(c for c, _, _ in cols)} FROM read_files('{VOL}/raw_files/tables/{name}.csv', format => 'csv', header => true, schema => '{schema}')""")

display(spark.sql(f"""
  SELECT 'products' AS table_name, count(*) AS rows FROM {S}.products
  UNION ALL SELECT 'production_lots', count(*) FROM {S}.production_lots
  UNION ALL SELECT 'repair_requests', count(*) FROM {S}.repair_requests"""))


# COMMAND ----------

display(spark.sql(f"SELECT request_id, received_at, model_no, symptom_category, result_category, operator_memo FROM {S}.repair_requests ORDER BY received_at DESC LIMIT 5"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. モデル・AI関数・SQL ウェアハウスが使えるかを確かめる

# COMMAND ----------

for role, name in [("エージェントのモデル", LLM_ENDPOINT), ("LLM ジャッジのモデル", JUDGE_ENDPOINT), ("埋め込みモデル", EMBEDDING_ENDPOINT)]:
    body = {"input": ["テスト"]} if role == "埋め込みモデル" else {"messages": [{"role": "user", "content": "OKとだけ答えて"}], "max_tokens": 10}
    try:
        _w.api_client.do("POST", f"/serving-endpoints/{name}/invocations", body=body)
        checks.append((role, "OK", name))
    except Exception as e:
        msg = str(e)
        if "PERMISSION" in msg or "403" in msg:
            checks.append((role, "NG", f"{name} を呼び出す権限がない。管理者に依頼する"))
        else:
            checks.append((role, "NG", f"{name}: {msg[:120]}（なければ 00_設定 で別のモデルを指定する）"))

for fn, sql in [("ai_mask", "SELECT ai_mask('佐藤 花子様（090-1234-5678）', array('person', 'phone'))"),
                ("ai_prep_search", "SELECT ai_prep_search('テスト')"),
                ("ai_parse_document", "SELECT ai_parse_document(unhex('255044462D312E340A')) IS NOT NULL")]:
    try:
        spark.sql(sql).collect()
        checks.append((f"AI関数 {fn}", "OK", ""))
    except Exception as e:
        msg = str(e)
        if any(k in msg for k in ("PERMISSION_DENIED", "Preview", "not available", "not supported", "region", "UNRESOLVED_ROUTINE")):
            checks.append((f"AI関数 {fn}", "NG", "管理者が Previews で「AI Prep Search」を有効にする" if "Preview" in msg else msg[:150]))
        else:   # 入力が不正などのエラーは、関数そのものは使えるとみなす
            checks.append((f"AI関数 {fn}", "OK", ""))

checks.append(("SQL ウェアハウス", "OK" if WAREHOUSE_ID else "NG",
               WAREHOUSE_ID or "トレースを読むのに必要。管理者に、SQL ウェアハウスと CAN USE の付与を依頼する"))

result = pd.DataFrame(checks, columns=["項目", "結果", "補足"])
display(result)
ng = result[result["結果"] != "OK"]
if len(ng):
    print("「NG」の項目を確認してください:\n" + ng.to_string(index=False))

# COMMAND ----------

# MAGIC %md
# MAGIC 実行が終わったら、説明に戻ります。説明のあとで `02_データパイプライン` に進みます。
