# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 特徴量テーブルの構築
# MAGIC
# MAGIC **このノートブックのゴール**
# MAGIC 再利用可能な **特徴量テーブル** を Unity Catalog 上に3つ作ります。
# MAGIC - `customer_features`（顧客の静的属性）
# MAGIC - `merchant_features`（加盟店の集計特徴量）
# MAGIC - `login_features`（ログイン履歴からの**時系列**特徴量）
# MAGIC
# MAGIC ※ 作った特徴量テーブルを使った学習セットの作成（`FeatureLookup` / `create_training_set`）は
# MAGIC 次の `02_train_register` で扱います。
# MAGIC
# MAGIC ---
# MAGIC ### 💡 使用する Databricks 機能：Feature Engineering in Unity Catalog（特徴量ストア）
# MAGIC 特徴量を **Unity Catalog 上の Delta テーブル**として一元管理し、学習・推論で同じ定義を再利用する仕組みです。
# MAGIC
# MAGIC 📖 概要: https://docs.databricks.com/aws/ja/machine-learning/feature-store/
# MAGIC
# MAGIC 📖 Python API: https://docs.databricks.com/aws/ja/machine-learning/feature-store/python-api
# MAGIC
# MAGIC **本シナリオでの効き方**：不正検知に効く「顧客・加盟店・ログイン」の特徴量を **組織の再利用資産** として整備でき、
# MAGIC 学習時と推論時で特徴量計算がズレる *Train/Serve Skew* を防げます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. ライブラリ準備と共通設定の読み込み

# COMMAND ----------

# 特徴量ストアのクライアント(databricks-feature-engineering)と、モデル関連ライブラリを導入
# %pip は notebook スコープでインストールされ、restartPython() で有効化される
%pip install -q "mlflow>=2.22.0" "databricks-feature-engineering>=0.16.0" "lightgbm>=4.0.0"
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## `FeatureEngineeringClient` について
# MAGIC `FeatureEngineeringClient` は、**Feature Engineering in Unity Catalog を Python から操作するためのメインクライアント**です。
# MAGIC 特徴量テーブルの作成（`create_table`）・書き込み（`write_table`）・学習セット作成（`create_training_set`）・
# MAGIC モデルへの特徴量ロジック同梱（`log_model`）・バッチ推論（`score_batch`）を、すべてこの1つのクライアント経由で行います。
# MAGIC このノートブック以降（02〜04）でも同じ `fe = FeatureEngineeringClient()` を使い回します。
# MAGIC
# MAGIC 📖 FeatureEngineeringClient（AWS 日本語版ドキュメント）: https://docs.databricks.com/aws/ja/machine-learning/feature-store/python-api

# COMMAND ----------

# FeatureEngineeringClient は特徴量テーブルの作成・書き込み・学習連携を行うメインAPI
from databricks.feature_engineering import FeatureEngineeringClient
from pyspark.sql import functions as F, Window

fe = FeatureEngineeringClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 顧客特徴量テーブル（静的・主キー: customer_id）
# MAGIC 顧客マスタ `m_customers` から、モデルが使いやすい形の属性を作ります。
# MAGIC
# MAGIC ### 💡 使用する機能：特徴量テーブルの作成（`fe.create_table`）
# MAGIC `primary_keys` を指定して UC 上に特徴量テーブルを作成します（主キーは後から変更不可）。
# MAGIC
# MAGIC 📖 https://docs.databricks.com/aws/ja/machine-learning/feature-store/python-api
# MAGIC
# MAGIC **本シナリオでの効き方**：`customer_id` をキーにすることで、この顧客特徴量は不正検知だけでなく
# MAGIC 与信・解約予測など **他モデルからも同じ定義で再利用** できます。
# MAGIC また `primary_device_id` / `prefecture` を含めておくと、後段のモデルで「取引のデバイス・地域が
# MAGIC 顧客の普段の値と一致するか（＝なりすまし兆候）」を判定できます。

# COMMAND ----------

customer_feat = spark.sql(f"""
  SELECT
    customer_id,                                              -- 主キー（顧客ID）
    FLOOR(DATEDIFF(CURRENT_DATE(), birth_date) / 365)  AS age,          -- 生年月日 → 年齢
    DATEDIFF(CURRENT_DATE(), registration_date)        AS tenure_days,  -- 登録からの経過日数（口座の古さ）
    avg_monthly_spend,                                       -- 平均月間利用額（後で金額比率の分母に使う）
    telecom_plan,                                            -- 契約プラン（カテゴリ特徴量）
    customer_status,                                         -- 顧客ステータス（カテゴリ特徴量）
    primary_device_id,                 -- 取引の device_id と突合して「デバイス不一致」を作るのに使う
    prefecture AS cust_prefecture      -- 取引の transaction_prefecture と突合して「地域不一致」を作るのに使う
  FROM {SRC}.m_customers
""")

# create_table: 主キーを指定して UC 上に特徴量テーブルを作成（df からスキーマとデータを登録）
fe.create_table(
    name=CUSTOMER_FEATURES,          # 例: <catalog>.<work_schema>.customer_features
    primary_keys=["customer_id"],    # 一意キー
    df=customer_feat,                # 登録するデータ
    description="顧客の静的属性特徴量（年齢・継続日数・平均利用額・プラン・ステータス・主デバイス・居住県）",
)
print(f"created: {CUSTOMER_FEATURES}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 加盟店特徴量テーブル（集計・主キー: merchant_id）
# MAGIC 加盟店マスタ + 過去取引から、加盟店ごとのリスク傾向（過去の不正率・平均取引額など）を集計します。
# MAGIC
# MAGIC > 🔎 **リーク防止の工夫**：`merchant_fraud_rate` などの集計は **学習期間（`TRAIN_END` より前）だけ** で計算します。
# MAGIC > 推論対象期間の情報を使わないことで、加盟店統計にも未来情報が混ざらないようにします。
# MAGIC
# MAGIC **本シナリオでの効き方**：加盟店の過去不正率は不正検知の強い手掛かり。特徴量テーブル化しておけば
# MAGIC 再学習のたびに最新値へ更新でき、モデル側は同じキーで参照するだけで済みます。

# COMMAND ----------

merchant_feat = spark.sql(f"""
  SELECT
    m.merchant_id,                                           -- 主キー（加盟店ID）
    m.category,                                              -- 業種カテゴリ（カテゴリ特徴量）
    m.prefecture AS merchant_prefecture,                     -- 加盟店の所在県（カテゴリ特徴量）
    -- 過去の不正率（学習期間の取引のみで平均）。COALESCE で取引実績のない加盟店は 0 に
    COALESCE(AVG(CASE WHEN p.is_fraud THEN 1.0 ELSE 0.0 END), 0) AS merchant_fraud_rate,
    COALESCE(AVG(p.amount), 0)                                   AS merchant_avg_amount,   -- 平均取引額
    COUNT(p.payment_id)                                          AS merchant_txn_count     -- 取引件数（信頼度の目安）
  FROM {SRC}.m_merchants m
  LEFT JOIN {SRC}.t_payments p
    ON  m.merchant_id = p.merchant_id
    AND p.payment_timestamp < '{TRAIN_END}'   -- ★学習期間だけで集計（リーク防止）
  GROUP BY m.merchant_id, m.category, m.prefecture
""")

fe.create_table(
    name=MERCHANT_FEATURES,
    primary_keys=["merchant_id"],
    df=merchant_feat,
    description="加盟店の集計特徴量（学習期間の不正率・平均取引額・取引件数）",
)
print(f"created: {MERCHANT_FEATURES}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. ログイン時系列特徴量テーブル（Point-in-Time 用・主キー: customer_id + login_timestamp）
# MAGIC ログイン履歴 `t_login_events` から、時間とともに変化する行動特徴量（直近の失敗ログイン数など）を作ります。
# MAGIC
# MAGIC ### 💡 使用する機能：時系列特徴量テーブル（`timeseries_column`）
# MAGIC 特徴量テーブルに **時系列キー** を持たせると、学習セット作成時に **Point-in-Time（as-of）結合** が可能になり、
# MAGIC 「ラベル時刻より前の特徴量だけ」を自動で結合できます。引数名は `databricks-feature-engineering>=0.16.0` で
# MAGIC **`timeseries_column`（単数）** です。
# MAGIC
# MAGIC 📖 https://docs.databricks.com/aws/ja/machine-learning/feature-store/time-series
# MAGIC
# MAGIC **本シナリオでの効き方**：「取引直前24hの失敗ログイン数」は不正の強い兆候ですが、うっかり *取引より後* の
# MAGIC ログインを混ぜると **ラベルリーケージ** になります。時系列特徴量テーブルにすることで、この漏洩を仕組みで防げます。
# MAGIC
# MAGIC `login_timestamp` は実時刻を持つため `(customer_id, login_timestamp)` はほぼ一意です。
# MAGIC よって各ログイン時点での **直近24hの失敗数・ログイン数** を直接ローリング集計します（日次集計は不要）。

# COMMAND ----------

# 顧客ごと・ログイン時刻順に、「直近24時間」の範囲窓を定義する。
#   - orderBy は unix 秒（cast("long")）にして、rangeBetween を「秒数」で指定できるようにする
#   - rangeBetween(-24*3600, 0) = 現在行の時刻から遡って24時間前まで
w24 = Window.partitionBy("customer_id").orderBy(F.col("login_timestamp").cast("long")).rangeBetween(-24 * 3600, 0)

login_feat = (
    spark.table(f"{SRC}.t_login_events")
    # 直近24hの「失敗ログイン数」：is_success=false を 1 として範囲窓で合計
    .withColumn("recent24h_fail_cnt",
                F.sum(F.when(~F.col("is_success"), 1).otherwise(0)).over(w24))
    # 直近24hの「ログイン総数」：窓内の行数
    .withColumn("recent24h_login_cnt", F.count("*").over(w24))
    # 特徴量テーブルに必要な列だけを残す（主キー2列 + 特徴量2列）
    .select("customer_id", "login_timestamp", "recent24h_fail_cnt", "recent24h_login_cnt")
    # 万一同一秒に複数ログインがあると主キーが重複するため、念のため一意化
    .dropDuplicates(["customer_id", "login_timestamp"])
)

# 時系列特徴量テーブルは「スキーマだけ先に作成 → write_table で投入」する2段構え。
# timeseries_column を指定することで Point-in-Time 結合が有効になる。
fe.create_table(
    name=LOGIN_FEATURES,
    primary_keys=["customer_id", "login_timestamp"],   # 時系列列も主キーに含める
    timeseries_column="login_timestamp",               # ← 時系列キー（>=0.16.0 の正式名。単数形）
    schema=login_feat.schema,                          # まずスキーマだけ登録
    description="ログイン履歴からの時系列特徴量（直近24hの失敗数・ログイン数、Point-in-Time 用）",
)
# データを投入（mode="merge" は主キーで upsert。再実行しても冪等）
fe.write_table(name=LOGIN_FEATURES, df=login_feat, mode="merge")
print(f"created: {LOGIN_FEATURES}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ まとめ
# MAGIC 3つの特徴量テーブルを Unity Catalog 上に作成しました。
# MAGIC - これらは **Catalog Explorer** の作業スキーマから確認でき、リネージ追跡の対象になります。
# MAGIC   📖 リネージ: https://docs.databricks.com/aws/ja/data-governance/unity-catalog/data-lineage
# MAGIC - 次の `02_train_register` で、`FeatureLookup` と `create_training_set` を使ってこれらを
# MAGIC   決済ラベルに **Point-in-Time 結合** し、学習セットを作ってモデルを学習・登録します。

# COMMAND ----------

print("Feature tables created:")
for t in [CUSTOMER_FEATURES, MERCHANT_FEATURES, LOGIN_FEATURES]:
    print(" -", t)