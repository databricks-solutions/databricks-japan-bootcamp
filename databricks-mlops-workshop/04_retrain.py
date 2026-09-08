# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 再学習パイプライン（検証 → 本番との品質比較 → 条件付き昇格）
# MAGIC
# MAGIC **このノートブックのゴール**
# MAGIC 1. 特徴量を最新化し、最新ラベルまで含めて **再学習**（challenger を作る）
# MAGIC 2. challenger を UC に **新バージョンとして登録**
# MAGIC 3. 本番稼働中（`@champion`）と challenger を **同じホールドアウトで品質比較**
# MAGIC 4. **challenger の方が良い場合だけ** `@champion` を新バージョンへ付け替え（＝本番昇格）。悪ければ本番は据え置き
# MAGIC
# MAGIC ---
# MAGIC ### 💡 使用する Databricks 機能：特徴量テーブル更新 + 再学習 + エイリアスによる安全な昇格
# MAGIC 特徴量を `write_table(mode="merge")` で差分更新し、同じ特徴量定義で再学習して新バージョンを登録します。
# MAGIC 本番切替は **評価ゲート（champion に勝った時だけ昇格）** を通すことで、劣化モデルの誤昇格を防ぎます。
# MAGIC
# MAGIC 📖 特徴量テーブル: https://docs.databricks.com/aws/ja/machine-learning/feature-store/python-api
# MAGIC
# MAGIC 📖 モデルのエイリアス: https://docs.databricks.com/aws/ja/machine-learning/manage-model-lifecycle/
# MAGIC
# MAGIC **本シナリオでの効き方**：新しく判明した不正ラベルを取り込んで鮮度を保ちつつ、品質が上がった時だけ本番に出せます。

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=2.22.0" "databricks-feature-engineering>=0.16.0" "lightgbm>=4.0.0"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

import mlflow
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from pyspark.sql import functions as F, Window
from mlflow import MlflowClient

fe = FeatureEngineeringClient()
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)
client = MlflowClient(registry_uri="databricks-uc")

# COMMAND ----------

# ラベル抽出のヘルパー: t_payments から学習/推論用のラベル DataFrame を作る
#   返す列: 結合キー(customer_id, merchant_id) + Point-in-Time用(payment_timestamp)
#           + 取引属性(amount, device_type, transaction_prefecture, device_id) + ラベル(is_fraud)
def build_labels(start=None, end=None, sample_fraction=1.0, seed=42):
    df = spark.table(f"{SRC}.t_payments")
    if start:
        df = df.where(F.col("payment_timestamp") >= F.lit(start))
    if end:
        df = df.where(F.col("payment_timestamp") < F.lit(end))
    df = df.select(
        "customer_id", "merchant_id", "payment_id", "payment_timestamp",
        "amount", "device_type", "transaction_prefecture", "device_id",
        F.col("is_fraud").cast("int").alias("is_fraud"),
    )
    if sample_fraction and sample_fraction < 1.0:
        df = df.sample(withReplacement=False, fraction=sample_fraction, seed=seed)
    return df

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 特徴量テーブルを最新データで更新
# MAGIC ### 💡 使用する機能：`write_table(mode="merge")`（差分更新 / upsert）
# MAGIC 主キーをもとに既存行を更新・新規行を追加します。実運用では日次などでこの更新が回るイメージです。
# MAGIC ここでは最初のノートブックと同じロジックでログイン時系列特徴量を再計算し、冪等に更新します。

# COMMAND ----------

# 各ログイン時点で「直近24hの失敗数・ログイン数」を再計算（01_feature_engineering と同じ定義）
w24 = Window.partitionBy("customer_id").orderBy(F.col("login_timestamp").cast("long")).rangeBetween(-24 * 3600, 0)
login_feat = (
    spark.table(f"{SRC}.t_login_events")
    .withColumn("recent24h_fail_cnt", F.sum(F.when(~F.col("is_success"), 1).otherwise(0)).over(w24))
    .withColumn("recent24h_login_cnt", F.count("*").over(w24))
    .select("customer_id", "login_timestamp", "recent24h_fail_cnt", "recent24h_login_cnt")
    .dropDuplicates(["customer_id", "login_timestamp"])
)
# merge で upsert（主キー: customer_id, login_timestamp）
fe.write_table(name=LOGIN_FEATURES, df=login_feat, mode="merge")
print("login_features updated (merge)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 最新ラベルまで含めて学習セットを再作成
# MAGIC `build_labels(end=None)` で **全期間**（旧・推論期間も含む）のラベルを使い、
# MAGIC 「新しく判明した不正ラベルを取り込んで学習し直す」動きを再現します。
# MAGIC 特徴量の結合定義（`feature_lookups`）は最初の学習と **完全に同一** です。

# COMMAND ----------

feature_lookups = [
    FeatureLookup(table_name=CUSTOMER_FEATURES, lookup_key="customer_id"),
    FeatureLookup(table_name=MERCHANT_FEATURES, lookup_key="merchant_id"),
    FeatureLookup(table_name=LOGIN_FEATURES, lookup_key="customer_id",
                  timestamp_lookup_key="payment_timestamp"),   # Point-in-Time 結合
]

training_set = fe.create_training_set(
    df=build_labels(end=None, sample_fraction=SAMPLE_FRACTION),   # 全期間
    feature_lookups=feature_lookups,
    label="is_fraud",
    exclude_columns=["customer_id", "merchant_id", "payment_id", "payment_timestamp"],
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. challenger を再学習して UC に新バージョン登録
# MAGIC 最初の学習と同じ **前処理込み Pipeline**（派生特徴量 → エンコード → LightGBM）で学習します。
# MAGIC ここではまだ本番（`@champion`）には昇格させず、**新バージョン（challenger）として登録するだけ** です。

# COMMAND ----------

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OrdinalEncoder, FunctionTransformer
from lightgbm import LGBMClassifier

# 学習ノートブックと同一の派生ロジック（自己完結形。cloudpickle で同梱される）
def derive_features(df):
    import pandas as pd
    d = pd.DataFrame(index=df.index)
    d["device_mismatch"] = (df["device_id"].astype(str) != df["primary_device_id"].astype(str)).astype(int)
    d["geo_mismatch"]    = (df["transaction_prefecture"].astype(str) != df["cust_prefecture"].astype(str)).astype(int)
    d["amount_ratio"]    = df["amount"].astype(float) / (df["avg_monthly_spend"].astype(float).fillna(0) + 1000)
    for c in ["age", "tenure_days", "avg_monthly_spend", "amount",
              "merchant_fraud_rate", "merchant_avg_amount", "merchant_txn_count",
              "recent24h_fail_cnt", "recent24h_login_cnt"]:
        d[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["device_type", "telecom_plan", "customer_status", "category", "merchant_prefecture"]:
        d[c] = df[c].astype(str)
    return d

# 学習データを準備（層化分割）
from sklearn.model_selection import train_test_split
pdf = training_set.load_df().toPandas()
y = pdf.pop("is_fraud")
X = pdf
X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

# 前処理込み Pipeline を構築して学習
best_params = {"n_estimators": 400, "num_leaves": 63, "scale_pos_weight": 10}  # 運用では前回champion設定を引き継ぐ
pre = ColumnTransformer(
    [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1), CAT_COLS)],
    remainder="passthrough",
)
challenger = Pipeline([
    ("derive", FunctionTransformer(derive_features, validate=False)),
    ("pre", pre),
    ("lgbm", LGBMClassifier(**best_params, random_state=42)),
]).fit(X_tr, y_tr)

# challenger を新バージョンとして登録（champion はまだ変更しない）
with mlflow.start_run(run_name="retrain_challenger"):
    fe.log_model(
        model=challenger,
        artifact_path="model",
        flavor=mlflow.sklearn,
        training_set=training_set,
        registered_model_name=MODEL_NAME,
        serialization_format="cloudpickle",
    )
# 登録された最新バージョン番号（＝challenger）を取得
challenger_version = max(client.search_model_versions(f"name='{MODEL_NAME}'"), key=lambda v: int(v.version)).version
print(f"registered challenger: {MODEL_NAME} v{challenger_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 本番（champion）と challenger を同じホールドアウトで品質比較
# MAGIC ### 💡 使用する機能：`fe.score_batch`（特徴量ストア連携推論）で公平に比較
# MAGIC 同一のホールドアウト（正解ラベル付き）を、champion と challenger の **両方の登録バージョンで推論** し、
# MAGIC F1 スコアで比較します。特徴量は両者とも自動ルックアップされるため、条件をそろえた比較になります。

# COMMAND ----------

from sklearn.metrics import f1_score, recall_score, precision_score

# ホールドアウト（学習後半期間を検証に使用。keys + 取引属性 + 正解ラベル）
holdout = build_labels(start=TRAIN_END, sample_fraction=0.3)
score_input   = holdout.drop("is_fraud")               # 推論入力（キー + 取引属性）
labels_lookup = holdout.select("payment_id", "is_fraud")  # 正解ラベル（payment_id で後で結合）

def evaluate_version(model_uri):
    """指定モデルURIでホールドアウトを推論し、F1/recall/precision を返す。"""
    preds = fe.score_batch(model_uri=model_uri, df=score_input, result_type="int")
    joined = preds.select("payment_id", "prediction").join(labels_lookup, "payment_id").toPandas()
    return {
        "f1":        f1_score(joined["is_fraud"], joined["prediction"]),
        "recall":    recall_score(joined["is_fraud"], joined["prediction"]),
        "precision": precision_score(joined["is_fraud"], joined["prediction"], zero_division=0),
    }

# challenger を評価
challenger_metrics = evaluate_version(f"models:/{MODEL_NAME}/{challenger_version}")
print("challenger:", {k: round(v, 4) for k, v in challenger_metrics.items()})

# 現在の champion を評価（存在すれば）
try:
    champ_mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    champion_metrics = evaluate_version(f"models:/{MODEL_NAME}@champion")
    print(f"champion (v{champ_mv.version}):", {k: round(v, 4) for k, v in champion_metrics.items()})
    have_champion = True
except Exception as e:
    print("no champion yet -> challenger を無条件で昇格します")
    have_champion = False

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 条件付き昇格
# MAGIC challenger の F1 が champion を上回った場合のみ `@champion` を challenger に付け替えます。
# MAGIC 比較結果は MLflow の Run にも記録します。

# COMMAND ----------

# 昇格判定（champion が無ければ無条件昇格）
promote = (not have_champion) or (challenger_metrics["f1"] > champion_metrics["f1"])

with mlflow.start_run(run_name="promotion_decision"):
    mlflow.log_metric("challenger_f1", challenger_metrics["f1"])
    if have_champion:
        mlflow.log_metric("champion_f1", champion_metrics["f1"])
    mlflow.log_param("promoted", promote)
    mlflow.log_param("challenger_version", challenger_version)

if promote:
    # 本番昇格：champion エイリアスを challenger バージョンへ付け替え
    client.set_registered_model_alias(MODEL_NAME, "champion", challenger_version)
    print(f"✅ 昇格しました: {MODEL_NAME}@champion -> v{challenger_version}")
    print("   → バッチ推論ジョブ(03_batch_inference)は無変更で新モデルを使い始めます。")
else:
    print(f"⏸ 据え置き: challenger(v{challenger_version}) は champion(v{champ_mv.version}) を上回らなかったため、"
          f"本番は現状維持です（challenger は登録のみ）。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. この再学習ノートブックを Lakeflow Job 化する（UI 手順）
# MAGIC ### 💡 使用する Databricks 機能：Lakeflow Jobs（定期実行のオーケストレーション）
# MAGIC 再学習は本来、手動ではなく **定期実行するジョブ** にします。スケジュールで自動的に
# MAGIC 「再学習 → 検証 → 条件付き昇格」が回り、品質が上がった時だけ本番が更新されます。
# MAGIC 📖 Lakeflow Jobs: https://docs.databricks.com/aws/ja/jobs/
# MAGIC 📖 スケジュールとトリガー: https://docs.databricks.com/aws/ja/jobs/scheduled
# MAGIC
# MAGIC **手順（ステップバイステップ）**
# MAGIC 1. 左メニュー **ジョブとパイプライン（Jobs & Pipelines）** → **ジョブを作成（Create job）**
# MAGIC 2. タスクを構成：タスク名 `retrain`、種類=**ノートブック**、パス=このノートブック（`04_retrain`）、コンピュート=**サーバーレス**
# MAGIC 3. **スケジュールとトリガー** で定期実行を設定（例：毎週 月曜 03:00 / cron `0 0 3 ? * MON`）
# MAGIC 4. **通知（Notifications）** に失敗時の通知先を設定
# MAGIC 5. （任意）特徴量更新を別タスクに分け、`refresh_features → retrain` の依存関係を持つ複数タスク構成にする
# MAGIC
# MAGIC > これで「定期再学習 → 検証 → 良ければ昇格」が自動で回る本番運用ループが完成します。