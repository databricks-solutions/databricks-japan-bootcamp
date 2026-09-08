# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 学習セット作成 → MLflow 実験管理 → Unity Catalog へのモデル登録
# MAGIC
# MAGIC **このノートブックのゴール**
# MAGIC 1. 特徴量テーブルを決済ラベルに **Point-in-Time 結合** して学習セットを作る（`FeatureLookup` / `create_training_set`）
# MAGIC 2. `autolog` + `mlflow.models.evaluate()` で複数試行を記録・自動評価し、実験 UI で比較
# MAGIC 3. `search_runs()` で **ベストランを検索** し、その（学習済みの）モデルを **特徴量メタ付き** で UC に登録、`@champion` を付与
# MAGIC
# MAGIC ---
# MAGIC ### 💡 使用する Databricks 機能：MLflow Tracking（実験管理）
# MAGIC 学習の1回1回を **Run** として記録し、複数試行を1つの **Experiment** にまとめて比較できます。
# MAGIC
# MAGIC 📖 実験管理: https://docs.databricks.com/aws/ja/mlflow/tracking
# MAGIC
# MAGIC 📖 実験(Experiments): https://docs.databricks.com/aws/ja/mlflow/experiments
# MAGIC
# MAGIC **本シナリオでの効き方**：不均衡な不正検知では *Accuracy* では差が見えず、**PR-AUC / Recall** で比較する必要があります。

# COMMAND ----------

# 必要ライブラリを導入（特徴量ストア連携 + LightGBM）
%pip install -q "mlflow>=2.22.0" "databricks-feature-engineering>=0.16.0" "lightgbm>=4.0.0"
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

import mlflow
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup

fe = FeatureEngineeringClient()

# レジストリを Unity Catalog に向ける
mlflow.set_registry_uri("databricks-uc")
# 試行結果(Run)を記録する箱として、「エクスペリメント」を用意
mlflow.set_experiment(EXPERIMENT)

# COMMAND ----------

# ラベル抽出のヘルパー: t_payments から学習/推論用のラベル DataFrame を作る
#   返す列: 結合キー(customer_id, merchant_id) + Point-in-Time用(payment_timestamp)
#           + 取引属性(amount, device_type, transaction_prefecture, device_id) + ラベル(is_fraud)
def build_labels(start=None, end=None, sample_fraction=1.0, seed=42):
    from pyspark.sql import functions as F
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
# MAGIC ## 1. FeatureLookup を定義して Point-in-Time 学習セットを作成
# MAGIC
# MAGIC ### 💡 使用する機能：`FeatureLookup` / 自動特徴量ルックアップ / `create_training_set`
# MAGIC `FeatureLookup` は「ラベル側のどのキーで、どの特徴量テーブルを結合するか」を宣言する定義です。
# MAGIC ここで作った定義は、
# MAGIC 1. 学習セット作成
# MAGIC 2. モデルへの同梱（`fe.log_model`）
# MAGIC 3. バッチ推論（`fe.score_batch`）
# MAGIC
# MAGIC で**すべて同じものが使われ**、学習と推論の特徴量計算の一致が保証されます。
# MAGIC
# MAGIC 📖 自動特徴量ルックアップ: https://docs.databricks.com/aws/ja/machine-learning/feature-store/automatic-feature-lookup
# MAGIC
# MAGIC 📖 学習セットの作成: https://docs.databricks.com/aws/ja/machine-learning/feature-store/train-models-with-feature-store
# MAGIC
# MAGIC **実装上のポイント**:
# MAGIC - `customer_features` / `merchant_features` … 主キー結合（静的特徴量）
# MAGIC - `login_features` … `timestamp_lookup_key="payment_timestamp"` を指定して **Point-in-Time 結合**
# MAGIC
# MAGIC   → 「取引時刻より前」のログイン特徴量だけが結合される（未来情報のリーク防止）

# COMMAND ----------

# ラベル DataFrame を取得（学習期間のみ・サンプリング）。00_setup の build_labels が返す列:
#   結合キー(customer_id, merchant_id) + Point-in-Time用(payment_timestamp)
#   + 取引属性(amount, device_type, transaction_prefecture, device_id) + ラベル(is_fraud)
labels = build_labels(end=TRAIN_END, sample_fraction=SAMPLE_FRACTION)

# 3つの特徴量テーブルの結合方法を宣言
feature_lookups = [
    # 顧客特徴量：customer_id で単純結合
    FeatureLookup(table_name=CUSTOMER_FEATURES, lookup_key="customer_id"),
    # 加盟店特徴量：merchant_id で単純結合
    FeatureLookup(table_name=MERCHANT_FEATURES, lookup_key="merchant_id"),
    # ログイン時系列特徴量：customer_id で結合しつつ、payment_timestamp を基準に Point-in-Time 結合
    FeatureLookup(table_name=LOGIN_FEATURES, lookup_key="customer_id",
                  timestamp_lookup_key="payment_timestamp"),
]

# create_training_set：ラベルに特徴量を結合した学習セットを作る。
#   この training_set オブジェクトは「どの特徴量からどう結合したか」のメタデータを保持し、
#   後で fe.log_model に渡すとモデルに特徴量取得ロジックが同梱される。
training_set = fe.create_training_set(
    df=labels,
    feature_lookups=feature_lookups,
    label="is_fraud",
    # 結合キー・ID・時刻列は「特徴量」ではないので除外（device_id 等の取引属性は特徴量として残す）
    exclude_columns=["customer_id", "merchant_id", "payment_id", "payment_timestamp"],
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 学習データの準備
# MAGIC 学習セットを pandas に変換し、特徴量 `X` とラベル `y` に分け、層化抽出で train/validation に分割します。
# MAGIC
# MAGIC > 💡 カテゴリ変数や突合フラグは **ここでは加工しません**。前処理はすべて後段の Pipeline に内包することで、
# MAGIC > 推論時とまったく同じ処理が保証されます（次セル参照）。

# COMMAND ----------

from sklearn.model_selection import train_test_split

# 学習セットを pandas 化（Point-in-Time 結合済みの全特徴量列 + ラベルが入っている）
pdf = training_set.load_df().toPandas()
y = pdf.pop("is_fraud")   # ラベルを取り出す
X = pdf                   # 残りが特徴量（生の列。突合や比率計算は Pipeline 側で行う）

print("fraud rate :", round(y.mean(), 4), " / rows:", len(y))

# 層化抽出（stratify=y）で不正の比率を train/val で揃える
X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 前処理込みモデル（Pipeline）の定義
# MAGIC Pipeline に **特徴量の派生 → カテゴリの序数エンコード → LightGBM** を内包します。派生ステップでは、
# MAGIC 取引属性と（特徴量ストアからルックアップした）顧客属性を突合して、不正検知に効く特徴量を生成します：
# MAGIC - `device_mismatch` = 取引 `device_id` ≠ 顧客 `primary_device_id`
# MAGIC - `geo_mismatch` = 取引 `transaction_prefecture` ≠ 顧客 `cust_prefecture`
# MAGIC - `amount_ratio` = 取引金額 ÷ 顧客の平均月間利用額
# MAGIC
# MAGIC > 🔎 **なぜ Pipeline に内包するのか**：後段の `fe.score_batch` は推論時に *生の特徴量* をモデルに渡します。
# MAGIC > **突合ロジックまで Pipeline に含める**ことで、学習時と推論時で同じ特徴量が再現され、*Train/Serve Skew* を防げます。

# COMMAND ----------

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OrdinalEncoder, FunctionTransformer
from lightgbm import LGBMClassifier

# 派生特徴量を作る関数。
#   cloudpickle でモデルに同梱されるよう、外部変数（グローバル）に依存しない自己完結形にする。
def derive_features(df):
    import pandas as pd
    d = pd.DataFrame(index=df.index)
    # なりすまし兆候：取引デバイスが顧客の主デバイスと違う → 1
    d["device_mismatch"] = (df["device_id"].astype(str) != df["primary_device_id"].astype(str)).astype(int)
    # 地理的異常：取引地が顧客の居住県と違う → 1
    d["geo_mismatch"]    = (df["transaction_prefecture"].astype(str) != df["cust_prefecture"].astype(str)).astype(int)
    # 高額異常：普段の利用額に対する取引額の比率（分母0対策で +1000）
    d["amount_ratio"]    = df["amount"].astype(float) / (df["avg_monthly_spend"].astype(float).fillna(0) + 1000)
    # そのまま使う数値特徴量（欠損は NaN のまま。LightGBM は NaN を扱える）
    for c in ["age", "tenure_days", "avg_monthly_spend", "amount",
              "merchant_fraud_rate", "merchant_avg_amount", "merchant_txn_count",
              "recent24h_fail_cnt", "recent24h_login_cnt"]:
        d[c] = pd.to_numeric(df[c], errors="coerce")
    # カテゴリ特徴量（後段の OrdinalEncoder が数値化する）
    for c in ["device_type", "telecom_plan", "customer_status", "category", "merchant_prefecture"]:
        d[c] = df[c].astype(str)
    return d

def make_pipeline(params):
    # カテゴリ列を序数エンコード、それ以外（派生済み数値）はそのまま通す
    pre = ColumnTransformer(
        transformers=[(
            "cat",
            # 未知カテゴリ/欠損は -1 に割り当て（推論時に学習時に無かった値が来ても落ちない）
            OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1),
            CAT_COLS,   # = device_type, telecom_plan, customer_status, category, merchant_prefecture
        )],
        remainder="passthrough",
    )
    # 派生 → エンコード → LightGBM の3段 Pipeline
    return Pipeline([
        ("derive", FunctionTransformer(derive_features, validate=False)),
        ("pre",    pre),
        ("lgbm",   LGBMClassifier(**params, random_state=42)),
    ])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 複数試行を記録し、`mlflow.models.evaluate()` で自動評価
# MAGIC
# MAGIC ### 💡 使用する機能：`autolog` と `mlflow.models.evaluate()`
# MAGIC - `mlflow.sklearn.autolog()` … パラメータ等を自動記録
# MAGIC - `mlflow.models.evaluate()` … 分類メトリクス（accuracy / precision / recall / f1 / ROC-AUC / PR-AUC 等）を
# MAGIC   **自動計算して Run に記録**（自前で sklearn 指標を計算しない）
# MAGIC   
# MAGIC 📖 autolog: https://docs.databricks.com/aws/ja/mlflow/quick-start
# MAGIC
# MAGIC ここでは `scale_pos_weight`（不均衡データで少数クラスを重視する重み）を変えて3試行します。

# COMMAND ----------

# autolog はパラメータ記録に使う。モデル成果物は各試行で明示的に log するため log_models=False。
mlflow.sklearn.autolog(log_models=False, silent=True)

# evaluate に渡す検証用データ（特徴量 + 正解ラベル列）。全試行で共通なので先に作る。
eval_pdf = X_val.copy()
eval_pdf["is_fraud"] = y_val.values

trials = [
    {"n_estimators": 200, "num_leaves": 31,  "scale_pos_weight": 1},
    {"n_estimators": 400, "num_leaves": 63,  "scale_pos_weight": 10},   # 不均衡対策
    {"n_estimators": 600, "num_leaves": 127, "scale_pos_weight": 30},
]

for params in trials:
    with mlflow.start_run(run_name=f"lgbm_spw{params['scale_pos_weight']}"):
        # 学習
        pipe = make_pipeline(params).fit(X_tr, y_tr)
        mlflow.log_params({f"lgbm_{k}": v for k, v in params.items()})
        # このモデルを Run に記録（evaluate はモデルURIを受け取って予測・評価する）。
        # LightGBM は既定の skops 保存で拒否されるため cloudpickle を明示。
        info = mlflow.sklearn.log_model(pipe, artifact_path="model", serialization_format="cloudpickle")
        # ★分類メトリクスを自動計算して Run に記録（SHAP等の重い説明生成は無効化）
        mlflow.models.evaluate(
            model=info.model_uri,
            data=eval_pdf,
            targets="is_fraud",
            model_type="classifier",
            evaluator_config={"log_model_explainability": False},
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🔎 実験 UI で比較する
# MAGIC 左メニュー **Experiments** → この実験を開き、3つの Run を選択して **Compare** してください。
# MAGIC `mlflow.models.evaluate()` が記録した指標が並び、**Accuracy では差が見えにくくても Recall / PR-AUC では
# MAGIC 明確に差が出る**ことが確認できます（不正検知は「取りこぼさない = Recall」が重要）。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. ベストランを検索し、そのモデルを Unity Catalog に登録
# MAGIC
# MAGIC ### 💡 使用する機能：`mlflow.search_runs()` + Models in Unity Catalog + `fe.log_model`
# MAGIC **同じ学習をやり直さず**、`search_runs()` で最良の Run を検索し、その **学習済みモデルをロード** して登録します。
# MAGIC
# MAGIC 📖 Models in Unity Catalog: https://docs.databricks.com/aws/ja/machine-learning/manage-model-lifecycle/
# MAGIC
# MAGIC `fe.log_model(training_set=...)` を使うと特徴量取得ロジックが同梱され、推論時（`score_batch`）に特徴量を自動結合できます。
# MAGIC
# MAGIC > ⚠️ LightGBM/ColumnTransformer は skops 既定保存で拒否されるため `serialization_format="cloudpickle"` を明示します。

# COMMAND ----------

# 実験内の試行 Run を検索し、選択指標が最大の Run を特定（＝再学習しない）
# 不均衡な不正検知では PR-AUC で選ぶ。mlflow.models.evaluate が記録する指標名 precision_recall_auc を直接指定する。
exp = mlflow.get_experiment_by_name(EXPERIMENT)
runs_df = mlflow.search_runs(
    experiment_ids=[exp.experiment_id],
    filter_string="tags.`mlflow.runName` LIKE 'lgbm_%'",
    order_by=["metrics.precision_recall_auc DESC"],
)
best_run_id = runs_df.iloc[0]["run_id"]
print(f"best run: {best_run_id}  (precision_recall_auc={runs_df.iloc[0]['metrics.precision_recall_auc']:.4f})")

# ベストランの学習済みモデルをロード（再学習せずに再利用）
best_pipe = mlflow.sklearn.load_model(f"runs:/{best_run_id}/model")

# 特徴量メタ付きで UC に登録（新しい登録専用の Run にまとめる）
with mlflow.start_run(run_name="register_champion"):
    fe.log_model(
        model=best_pipe,
        artifact_path="model",
        flavor=mlflow.sklearn,
        training_set=training_set,            # ← 特徴量取得ロジックを同梱（score_batch で自動結合）
        registered_model_name=MODEL_NAME,     # ← UC に登録
        serialization_format="cloudpickle",   # ← skops 既定保存の拒否を回避
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. `@champion` エイリアスを付与
# MAGIC 「今の本番モデルはどれか」を **エイリアス**（`@champion`）で表現します。推論側は常に `@champion` を参照するため、
# MAGIC モデルを差し替えても推論コードを変える必要がありません。
# MAGIC
# MAGIC 📖 https://docs.databricks.com/aws/ja/machine-learning/manage-model-lifecycle/

# COMMAND ----------

from mlflow import MlflowClient
client = MlflowClient(registry_uri="databricks-uc")

# 直前に登録した最新バージョンを取得し、champion を付け替える
latest = max(client.search_model_versions(f"name='{MODEL_NAME}'"), key=lambda v: int(v.version))
client.set_registered_model_alias(MODEL_NAME, "champion", latest.version)
print(f"{MODEL_NAME}@champion -> version {latest.version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🔎 Catalog Explorer で確認
# MAGIC 作業スキーマの Models から `fraud_detection_model` を開き、**バージョン / エイリアス / リネージ**
# MAGIC （モデル ↔ 特徴量テーブル ↔ 元データ）がつながっていることを確認してください。
# MAGIC 📖 リネージ: https://docs.databricks.com/aws/ja/data-governance/unity-catalog/data-lineage