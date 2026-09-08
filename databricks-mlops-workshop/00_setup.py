# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 00_setup — 環境セットアップ（共通ノートブック）
# MAGIC
# MAGIC このノートブックは **各ノートブック（01〜05）の冒頭で `%run ./00_setup` として読み込む** 共通設定です。
# MAGIC
# MAGIC ここで行うこと:
# MAGIC 1. カタログ名の指定（開催時はここだけ変更）
# MAGIC 2. 受講者ごとの **作業スキーマ** の作成（成果物の衝突回避）
# MAGIC 3. 全ノートブックで使う **共通変数** の定義

# COMMAND ----------

# MAGIC %md
# MAGIC ## カタログ名の指定
# MAGIC 以下のセルの `CATALOG`変数を管理者から案内されたカタログ名に書き換えてください。

# COMMAND ----------

# ===== 管理者から案内されたカタログ名に書き換えてください =====
CATALOG = "<ワークショップ用カタログ名>"

# COMMAND ----------

# MAGIC %md
# MAGIC # これより下のセルは変更不要

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマの設定
# MAGIC - `CATALOG`：ワークショップで使用する Unity Catalog カタログ（**開催時に変更**）
# MAGIC - `SRC_SCHEMA`：元データ（読み取り専用）
# MAGIC - `WORK_SCHEMA`：受講者ごとの作業スキーマ（自動で `mlops_ws_<ユーザー名>`）

# COMMAND ----------

SRC_SCHEMA = "mlops_ws_shared"  # 元データ（読み取り専用）

# 実行ユーザー名から作業スキーマ名を自動生成（受講者間でスキーマを分離）
USER = spark.sql("SELECT current_user()").first()[0]
USER_TOKEN = USER.split("@")[0].replace(".", "_").replace("-", "_")
WORK_SCHEMA = f"mlops_ws_{USER_TOKEN}"

# 作業スキーマを作成（存在すれば何もしない）
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{WORK_SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 共通変数（全ノートブックで参照）

# COMMAND ----------

SRC  = f"{CATALOG}.{SRC_SCHEMA}"   # 元データスキーマの完全名
WORK = f"{CATALOG}.{WORK_SCHEMA}"  # 作業スキーマの完全名

# 特徴量テーブル
CUSTOMER_FEATURES = f"{WORK}.customer_features"
MERCHANT_FEATURES = f"{WORK}.merchant_features"
LOGIN_FEATURES    = f"{WORK}.login_features"

# モデル・予測・実験
MODEL_NAME = f"{WORK}.fraud_detection_model"   # UC 登録モデル（catalog.schema.model）
PRED_TABLE = f"{WORK}.fraud_predictions"       # バッチ推論の出力テーブル
EXPERIMENT = f"/Users/{USER}/fraud_mlops_ws"   # MLflow 実験のパス

# 学習 / 推論の時間分割（この日付より前を学習、以降を推論検証に使う）
TRAIN_END = "2026-05-01"

# 学習データのサンプリング率（ハンズオンを軽快にするため既定 0.25。1.0 で全件）
SAMPLE_FRACTION = 0.25

# モデルのカテゴリ特徴量（Pipeline の派生ステップ後に序数エンコードする列）
# ※ device_id / transaction_prefecture / primary_device_id / cust_prefecture は
#    派生特徴量（device_mismatch / geo_mismatch）を作った後に破棄するため、ここには含めない
CAT_COLS = [
    "device_type",                    # 取引の属性
    "telecom_plan", "customer_status",  # 顧客の属性
    "category", "merchant_prefecture",  # 加盟店の属性
]

print(f"USER        = {USER}")
print(f"SRC         = {SRC}")
print(f"WORK        = {WORK}")
print(f"MODEL_NAME  = {MODEL_NAME}")
print(f"EXPERIMENT  = {EXPERIMENT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ セットアップ完了。呼び出し元ノートブックでは、この後 `SRC` / `WORK` / `MODEL_NAME` などの
# MAGIC 変数がそのまま使えます。
# MAGIC （ラベル抽出のヘルパー `build_labels()` は、それを使う `02_train_register` / `04_retrain` の各ノートブック内で定義します。）