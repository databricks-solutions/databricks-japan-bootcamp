# Databricks notebook source
# MAGIC %md
# MAGIC # 06 追加データ投入｜そのまま運用に乗る
# MAGIC
# MAGIC 新しい事故2件（case_06・07）のファイルが届いた、という想定です。ファイルを置いて **01〜05 をもう一度実行** し、次の2点を確かめます。
# MAGIC
# MAGIC 1. **どの工程も、新しく届いた2件だけを処理した**：処理済みの5件をモデルに渡し直していない＝もう一度課金されていない
# MAGIC 2. **Gold には7件がそろい、新しい2件の食い違いも見つかる**
# MAGIC
# MAGIC ### なぜ新しい2件だけが処理されるのか
# MAGIC
# MAGIC | 工程 | 「処理済み」をどう判断しているか |
# MAGIC |---|---|
# MAGIC | 01 Bronze | Auto Loader が、取り込んだファイルをチェックポイントに記録している |
# MAGIC | 02〜04 Silver | Bronze の行のうち、Silver に同じ `path` の行が無いものだけを選んでいる（`LEFT ANTI JOIN`） |
# MAGIC | 05 Gold | LLM を呼ばないので、毎回すべてを作り直す |
# MAGIC
# MAGIC 本番では、01〜05 をそのままジョブのタスクにし、`landing/` にファイル到着トリガーを付ければ、ファイルが届くたびに自動で実行されます。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2回目のサンプルデータを置く
# MAGIC
# MAGIC リポジトリの `data` フォルダから、case_06・07 の3形式を `landing/` にコピーします。出力で、各形式のファイルが7件ずつになったことを確かめてください。

# COMMAND ----------

import shutil

for m in MODALITIES:
    for name in sorted(os.listdir(f"{DATA_DIR}/{m}")):
        if name.startswith("case_06.") or name.startswith("case_07."):
            shutil.copyfile(f"{DATA_DIR}/{m}/{name}", f"{LANDING}/{m}/{name}")
    print(f"{m:6s}:", sorted(os.listdir(f"{LANDING}/{m}")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 01〜05 をもう一度実行する
# MAGIC
# MAGIC 01〜05 を順に開いて「すべて実行」しても同じです。ここでは、このノートブックから `dbutils.notebook.run` で順に実行します（全体で3〜4分かかります）。
# MAGIC 呼び出しの順番は、ジョブにしたときのタスクの順番と同じです。

# COMMAND ----------

import time

for nb in ["01_bronze_ingest", "02_silver_audio", "03_silver_image", "04_silver_form", "05_gold_join"]:
    t0 = time.time()
    dbutils.notebook.run(f"./{nb}", 1800, {"catalog": CATALOG})   # 1800：1本あたりの時間の上限（秒）
    print(f"{nb}: {time.time() - t0:.0f} 秒")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確かめる①：各工程は新しい2件だけを処理したか
# MAGIC
# MAGIC Silver の各行には、処理した時刻（`processed_at`）が入っています。同じ時刻の行は、同じ実行で処理されたものです。
# MAGIC 工程ごとに、1回目（5件：case_01〜05）と2回目（2件：case_06・07）の2つの時刻に分かれていれば、2回目は新しい2件だけをモデルに渡したことになります。

# COMMAND ----------

display(spark.sql(f"""
WITH s AS (
  SELECT '02 音声' AS step, case_id, processed_at FROM {SILVER_AUDIO}
  UNION ALL SELECT '03 写真', case_id, processed_at FROM {SILVER_IMAGE}
  UNION ALL SELECT '04 見積書', case_id, processed_at FROM {SILVER_FORM}
)
SELECT step AS `工程`, date_format(processed_at, 'HH:mm:ss') AS `処理した時刻`,
       count(*) AS `件数`, array_sort(collect_list(case_id)) AS `案件`
FROM s GROUP BY step, processed_at ORDER BY step, processed_at"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確かめる②：Gold に7件がそろい、新しい2件の食い違いも見つかるか
# MAGIC
# MAGIC case_07 は、通話では「右前のドア」と申告していますが、写真と見積書は左前のドアです。`findings` に「損傷位置の食い違い」が入っていることを確かめてください。

# COMMAND ----------

display(spark.sql(f"""
SELECT case_id, said_position, photo_position, estimate_position, said_severity, total, findings
FROM {GOLD} ORDER BY case_id"""))
