# Databricks notebook source
# MAGIC %md
# MAGIC # _config（共通設定）
# MAGIC
# MAGIC 各ノートブックの冒頭で `%run ./_config` として読み込む共通設定です。単体では実行しません。
# MAGIC
# MAGIC このノートブックでは、次のことをまとめて行います。
# MAGIC
# MAGIC 1. **名前を決める**：カタログ・スキーマ・Volume・テーブルの名前と、使うモデルの名前
# MAGIC 2. **置き場所を用意する**：スキーマ・Volume・ファイルを置くフォルダがなければ作る（あれば何もしない）
# MAGIC 3. **環境を確かめる**：このノートブックの環境で `ai_parse_document` が使えるかを確かめ、使えなければその場で止める
# MAGIC
# MAGIC 使うカタログを変えるときは、下の `DEFAULT_CATALOG` だけを書き換えてください。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 名前を決める
# MAGIC
# MAGIC - **スキーマ** は、ログインしているユーザー名から自動で作ります（例：`yamada.taro@example.com` → `ws_yamada_taro`）。参加者ごとに別のスキーマになるので、ほかの参加者のテーブルやファイルと混ざりません。
# MAGIC - **Volume** `raw` の中に、届いたファイルを置く `landing/`（形式ごとに `audio/`・`image/`・`form/`）と、Auto Loader が処理済みのファイルを記録する `_checkpoints/` を作ります。
# MAGIC - **選択肢**（損傷の位置・部位・程度）は、音声・写真・見積書の3つで同じものを使います。05 で3つを突き合わせるため、ここでそろえておきます。

# COMMAND ----------

import os
import re

# ===== 変更してよいのはここだけ =====
DEFAULT_CATALOG = "workspace"   # スキーマを作る権限（USE CATALOG・CREATE SCHEMA）があるカタログ
# ====================================

# ジョブから実行するときは、パラメータ catalog でカタログ名を上書きできる
try:
    CATALOG = dbutils.widgets.get("catalog")
except Exception:
    CATALOG = DEFAULT_CATALOG

# ユーザー名（メールアドレスの @ より前）から、英数字とアンダースコアだけのスキーマ名を作る
_user = spark.sql("SELECT current_user()").first()[0]
SCHEMA = "ws_" + re.sub(r"[^0-9a-zA-Z]+", "_", _user.split("@")[0]).strip("_").lower()

# ファイルの置き場所（Unity Catalog の Volume）
VOLUME = "raw"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
LANDING = f"{VOLUME_PATH}/landing"            # 届いたファイルを置く場所。形式ごとにフォルダを分ける
CHECKPOINT = f"{VOLUME_PATH}/_checkpoints"    # Auto Loader が「どのファイルまで処理したか」を記録する場所
MODALITIES = ["audio", "image", "form"]       # 音声・画像・帳票のフォルダ名

# サンプルデータの場所（このリポジトリの data フォルダ。ノートブックのフォルダの1つ上にある）
DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "data"))

# 使うモデル（いずれも Databricks の基盤モデル）
AUDIO_MODEL = "databricks-gemini-3-1-pro"     # 02：音声を直接入力できるモデル
IMAGE_MODEL = "databricks-gemini-3-5-flash"   # 03：画像を入力でき、ai_query の JSON スキーマ指定に対応するモデル

# テーブル名（カタログ.スキーマ.テーブル の3階層）
T = lambda name: f"{CATALOG}.{SCHEMA}.{name}"
BRONZE = T("bronze_files")        # 01：届いたファイルをそのまま1行＝1ファイルで持つ
SILVER_AUDIO = T("silver_audio")  # 02：通話音声から取り出した申告内容
SILVER_IMAGE = T("silver_image")  # 03：写真から取り出した損傷
SILVER_FORM = T("silver_form")    # 04：見積書から取り出した項目と検算の結果
GOLD = T("gold_cases")            # 05：事故1件＝1行にまとめ、食い違いを付けたもの

# 3つの形式で共通に使う選択肢（05 で突き合わせるため、そろえておく）
DAMAGE_POSITIONS = ["左前", "右前", "左後ろ", "右後ろ", "前", "後ろ"]
DAMAGE_PARTS = ["フロントバンパー", "リヤバンパー", "フロントドア", "リヤドア", "フロントガラス", "その他"]
SEVERITIES = ["軽微", "中程度", "大きい"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 置き場所を用意する
# MAGIC
# MAGIC `IF NOT EXISTS` を付けているので、何度実行しても同じ状態になります（2回目以降は何もしません）。

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")
for m in MODALITIES:
    os.makedirs(f"{LANDING}/{m}", exist_ok=True)   # Volume の中のフォルダは、ふつうのファイル操作で作れる

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 環境を確かめる
# MAGIC
# MAGIC `ai_parse_document`（04 で使う）は、公式ドキュメントではサーバレスの環境バージョン 3 以上が要件とされています（このノートブックは環境バージョン 1 と 4 で動作を確認しています）。使えない環境のまま進むと 04 で初めてエラーになるため、ここで先に確かめます。
# MAGIC 入力に NULL を渡して、関数が使えるかだけを確かめます（文書は解析しません）。

# COMMAND ----------

try:
    # 結果は真偽値にして受け取る（古い環境のノートブックは VARIANT 型の値をそのまま受け取れないため）
    spark.sql("SELECT ai_parse_document(CAST(NULL AS BINARY)) IS NULL AS ok").collect()
except Exception as e:
    raise RuntimeError(
        "このノートブックの環境では ai_parse_document が使えません。"
        "右側の「環境」パネルの「基本環境」で新しいバージョンを選び、「適用」してから実行し直してください。"
    ) from e

print(f"スキーマ : {CATALOG}.{SCHEMA}")
print(f"ファイル : {LANDING}")
