# Databricks notebook source
# MAGIC %md
# MAGIC # 00 セットアップ
# MAGIC
# MAGIC 自分のスキーマと Volume を作り、1回目のサンプルデータ（case_01〜05）を置きます。
# MAGIC
# MAGIC ## このハンズオンのシナリオ
# MAGIC
# MAGIC 損害保険の事故受付です。事故1件（受付番号 `case_id`）ごとに、次の3つのファイルが届きます。
# MAGIC
# MAGIC | 形式 | 中身 | 置き場所 |
# MAGIC |---|---|---|
# MAGIC | 音声 | 事故受付の通話録音（WAV） | `landing/audio/` |
# MAGIC | 画像 | 損害箇所の写真（JPEG） | `landing/image/` |
# MAGIC | 帳票 | 修理工場の見積書（PDF と、手書きの見積書をスキャンした JPEG） | `landing/form/` |
# MAGIC
# MAGIC 01〜05 で、この3つを共通の流れ（取り込む → AI で取り出す → 確かめる → つなぐ）で処理し、事故1件＝1行のテーブルにします。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 共通設定を読み込む
# MAGIC
# MAGIC カタログ・スキーマ・テーブルの名前などを `_config` から読み込みます。スキーマと Volume がなければ、ここで作られます。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## やり直すとき
# MAGIC
# MAGIC 最初からやり直したいときは、下のセルの `RESET = False` を `True` に書き換えて実行します。次のものを消します。
# MAGIC
# MAGIC - 01〜05 で作ったテーブル
# MAGIC - `landing/` に置いたファイル
# MAGIC - Auto Loader の処理済みの記録（`_checkpoints/`）。これを消さないと、同じファイルを置き直しても「処理済み」とみなされて取り込まれません
# MAGIC
# MAGIC 消したら `False` に戻してください。

# COMMAND ----------

import shutil

try:
    RESET = dbutils.widgets.get("reset").lower() == "true"   # ジョブから実行するときのパラメータ
except Exception:
    RESET = False   # やり直すときは True にする

if RESET:
    for t in [BRONZE, SILVER_AUDIO, SILVER_IMAGE, SILVER_FORM, GOLD]:
        spark.sql(f"DROP TABLE IF EXISTS {t}")
    for d in [LANDING, CHECKPOINT]:
        shutil.rmtree(d, ignore_errors=True)
    for m in MODALITIES:
        os.makedirs(f"{LANDING}/{m}", exist_ok=True)
    print("リセットしました")
else:
    print("リセットはしません")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1回目のサンプルデータを置く
# MAGIC
# MAGIC 「事故5件分のファイルが届いた」という状態を作ります。リポジトリの `data` フォルダから、case_01〜05 の3形式を自分の Volume の `landing/` にコピーします。
# MAGIC case_06・07 は、ハンズオン後半に 06 で置きます（新しく届いたファイルだけが処理されることを確かめるため）。
# MAGIC
# MAGIC 出力に、形式ごとに置いたファイルの一覧が表示されます。各形式に5ファイルずつあれば準備完了です。

# COMMAND ----------

def land(case_ids):
    """data/ から、指定した案件のファイルを landing/ の形式ごとのフォルダにコピーする"""
    for m in MODALITIES:
        for name in sorted(os.listdir(f"{DATA_DIR}/{m}")):
            if any(name.startswith(c + ".") for c in case_ids):
                shutil.copyfile(f"{DATA_DIR}/{m}/{name}", f"{LANDING}/{m}/{name}")
    # 音声は再配布にクレジットが必要なため、クレジットも一緒に置く
    shutil.copyfile(f"{DATA_DIR}/CREDITS.md", f"{VOLUME_PATH}/CREDITS.md")
    for m in MODALITIES:
        print(f"{m:6s}:", sorted(os.listdir(f"{LANDING}/{m}")))

land(["case_01", "case_02", "case_03", "case_04", "case_05"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## モデルを呼べるか確かめる
# MAGIC
# MAGIC 03 で使うモデルに、SQL の `ai_query` で短い質問を送ります。「準備完了」と返ってくれば、基盤モデルを呼べる状態です。

# COMMAND ----------

display(spark.sql(f"SELECT ai_query('{IMAGE_MODEL}', '「準備完了」とだけ返してください。') AS reply"))
