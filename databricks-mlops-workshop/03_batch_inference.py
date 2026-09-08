# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # バッチ推論 + Lakeflow Job 化
# MAGIC
# MAGIC **このノートブックのゴール**
# MAGIC 1. `@champion` モデルで、学習に使っていない **新規取引** をバッチ推論する
# MAGIC 2. 結果を予測テーブル `fraud_predictions` に書き込む
# MAGIC 3. このノートブックを **Lakeflow Job** として登録・スケジュール実行する（手順は末尾）
# MAGIC
# MAGIC ---
# MAGIC ### 💡 使用する Databricks 機能：特徴量ストア連携のバッチ推論（`fe.score_batch`）
# MAGIC 登録モデルで大量データを一括推論します。特徴量ストア連携モデルでは `fe.score_batch` に **キー列を渡すだけ** で、
# MAGIC モデルに同梱された特徴量取得ロジックが顧客・加盟店・ログインの特徴量を **自動ルックアップ** して推論します。
# MAGIC
# MAGIC 📖 バッチ推論: https://docs.databricks.com/aws/ja/machine-learning/model-inference/
# MAGIC
# MAGIC 📖 自動特徴量ルックアップ: https://docs.databricks.com/aws/ja/machine-learning/feature-store/automatic-feature-lookup
# MAGIC
# MAGIC **本シナリオでの効き方**：推論コード側に前処理・特徴量計算を一切書かないため、学習時と **完全に同じ特徴量** で
# MAGIC 推論されます（*Train/Serve Skew* なし）。

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=2.22.0" "databricks-feature-engineering>=0.16.0" "lightgbm>=4.0.0"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient
fe = FeatureEngineeringClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 推論対象データ（新規取引）を用意
# MAGIC 学習に使っていない **後半期間（`TRAIN_END` 以降）** の取引を「新規に到着した取引」に見立てます。
# MAGIC
# MAGIC > 🔎 **ここが重要**：`score_batch` に渡すのは **結合キー + Point-in-Time 用の時刻 + 取引属性** のみ。
# MAGIC > 顧客・加盟店・ログインの特徴量は **渡しません**（モデルが自動で取ってくる）。

# COMMAND ----------

from pyspark.sql import functions as F

new_txn = (
    spark.table(f"{SRC}.t_payments")
    # 学習に使っていない後半期間（TRAIN_END 以降）を「新規に到着した取引」に見立てる
    .where(F.col("payment_timestamp") >= F.lit(TRAIN_END))
    # score_batch に渡すのは「結合キー・時刻・取引属性」だけ。
    # 顧客/加盟店/ログインの特徴量は渡さない（モデルが自動でルックアップする）。
    .select(
        "customer_id", "merchant_id", "payment_id", "payment_timestamp",  # キー + Point-in-Time 用時刻
        "amount", "device_type", "transaction_prefecture", "device_id",   # 取引属性（派生特徴量の材料）
    )
)
print("rows to score:", new_txn.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. `score_batch` でバッチ推論
# MAGIC `model_uri` に `@champion` を指定するだけ。特徴量は自動ルックアップされます。

# COMMAND ----------

# score_batch：model_uri に @champion を指定するだけ。
#   モデルに同梱された特徴量取得ロジックが、customer/merchant/login の特徴量を自動結合し、
#   Pipeline の派生ステップが device_mismatch 等を計算して推論する（学習時と完全に同じ処理）。
preds = fe.score_batch(
    model_uri=f"models:/{MODEL_NAME}@champion",
    df=new_txn,
    result_type="int",   # 予測ラベル（0/1）を prediction 列に付与
)

# 保存する列を整理（キー + 予測 + 予測時刻）
out = preds.select(
    "payment_id", "customer_id", "merchant_id", "payment_timestamp", "amount",
    "prediction",
    F.current_timestamp().alias("scored_ts"),   # いつ推論したかを記録
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 予測テーブルに書き込み
# MAGIC 結果を Unity Catalog 上の Delta テーブルに保存します。後続処理（ダッシュボード・アラート等）はこのテーブルを参照します。

# COMMAND ----------

out.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(PRED_TABLE)

print(f"written: {PRED_TABLE}")
display(spark.table(PRED_TABLE).limit(20))

# 予測された不正件数の概観
display(spark.sql(f"""
  SELECT prediction, COUNT(*) AS cnt
  FROM {PRED_TABLE}
  GROUP BY prediction ORDER BY prediction
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Lakeflow Job 化（UI 手順）
# MAGIC
# MAGIC ### 💡 使用する Databricks 機能：Lakeflow Jobs（オーケストレーション）
# MAGIC 複数タスク（Notebook / SQL / パイプライン等）を依存関係でつなぎ、スケジュールやトリガーで実行する基盤です。
# MAGIC 失敗時の通知・リトライ、実行履歴の記録に対応し、サーバーレスで動かせます。
# MAGIC 📖 Lakeflow Jobs: https://docs.databricks.com/aws/ja/jobs/
# MAGIC 📖 タスクの構成: https://docs.databricks.com/aws/ja/jobs/configure-task
# MAGIC 📖 スケジュールとトリガー: https://docs.databricks.com/aws/ja/jobs/scheduled
# MAGIC
# MAGIC **本シナリオでの効き方**：手元での手動実行から、「毎日自動で・記録付きで・失敗したら通知」の
# MAGIC 不正スコアリング基盤に変わります。
# MAGIC
# MAGIC **手順（ステップバイステップ）**
# MAGIC 1. 左メニュー **ジョブとパイプライン（Jobs & Pipelines）** → **ジョブを作成（Create job）**
# MAGIC 2. タスクを構成：
# MAGIC    - タスク名 = `batch_inference`
# MAGIC    - 種類（Type）= **ノートブック（Notebook）**、パス = このノートブック（`03_batch_inference`）
# MAGIC    - コンピュート = **サーバーレス（Serverless）**
# MAGIC 3. **今すぐ実行（Run now）** で手動実行し、`fraud_predictions` が更新されることを確認
# MAGIC 4. **スケジュールとトリガー** でスケジュール追加（例：毎日 02:00 / cron `0 0 2 * * ?`）
# MAGIC 5. 必要に応じて **通知（Notifications）** に失敗時の通知先を設定