# Databricks notebook source
# MAGIC %md
# MAGIC # Lakeflow Designer ワークショップ — サンプルデータ生成
# MAGIC
# MAGIC このNotebookは、Lakeflow Designerワークショップで使用するサンプルデータを生成します。
# MAGIC
# MAGIC ## 生成されるデータ
# MAGIC | テーブル/ファイル | 種別 | 内容 |
# MAGIC |---|---|---|
# MAGIC | `sales_transactions` | ファクト | 売上トランザクション |
# MAGIC | `customer_master` | ディメンション | 顧客マスタ(属性 8 カラム) |
# MAGIC | `product_master` | ディメンション | 商品マスタ(属性 5 カラム) |
# MAGIC | `segment_targets.xlsx` | Excel ファイル | マーケ部門の月次目標(UC Volume 出力) |
# MAGIC
# MAGIC ## 埋め込み済みデータ傾向(主なもの)
# MAGIC - **時系列**: 年率 +10% 成長、12月 +30%、3月 +15%、7-8月 +20%、土日 +30%
# MAGIC - **顧客**: Basic 60% / Standard 30% / Premium 10%、客単価差、購買頻度差
# MAGIC - **年齢×カテゴリ**: 20-30代女性は Beauty/Apparel、40-50代男性は Electronics/Home
# MAGIC - **地域**: 関東 40% / 関西 20% / その他、都市部の Premium 比率高め
# MAGIC - **チャネル**: Online 45% / Store 40% / Mobile App 15%、世代別偏り
# MAGIC - **新商品効果**: 直近 6ヶ月内 launch 商品が売上の約 25%
# MAGIC - **割引**: 通常 30% / セール期間 60%、Basic の割引感応度高
# MAGIC
# MAGIC ## 使い方
# MAGIC
# MAGIC 1. **最初に「2. パラメータ設定(ウィジェット)」のセルまで実行** — これで画面上部にウィジェットが表示されます
# MAGIC 2. 画面上部の **「1. カタログ名(必須)」** に、データを書き込みたい Unity Catalog 上のカタログ名を入力
# MAGIC 3. その上で「Run all」(全セル実行)で残りのセルを実行
# MAGIC 4. 完了後、UC Catalog Explorer で生成されたテーブルとボリューム上の Excel を確認
# MAGIC
# MAGIC > **必須項目はカタログ名(`1. カタログ名(必須)`)のみ**です。その他のウィジェット項目はデフォルト値のままで問題ありません。動作確認やワークショップ規模の調整をしたい場合のみ変更してください。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 依存ライブラリのインストール

# COMMAND ----------

# MAGIC %pip install dbldatagen openpyxl --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. パラメータ設定(ウィジェット)

# COMMAND ----------

dbutils.widgets.text("catalog", "", "1. カタログ名(必須)")
dbutils.widgets.text("schema", "lakeflow_designer_workshop", "2. スキーマ名")
dbutils.widgets.text("num_customers", "5000", "3. 顧客数")
dbutils.widgets.text("num_products", "500", "4. 商品数")
dbutils.widgets.text("target_num_transactions", "50000", "5. 目標トランザクション数")
dbutils.widgets.text("months_back", "24", "6. 履歴の月数")
dbutils.widgets.dropdown("language", "ja", ["ja", "en"], "7. 言語")
dbutils.widgets.dropdown("reset_data", "false", ["true", "false"], "8. 既存テーブルを削除")

catalog = dbutils.widgets.get("catalog").strip()
schema = dbutils.widgets.get("schema")
num_customers = int(dbutils.widgets.get("num_customers"))
num_products = int(dbutils.widgets.get("num_products"))
target_num_transactions = int(dbutils.widgets.get("target_num_transactions"))
months_back = int(dbutils.widgets.get("months_back"))
language = dbutils.widgets.get("language")
reset_data = dbutils.widgets.get("reset_data") == "true"

# カタログ名は必須
if not catalog:
    raise ValueError(
        "ウィジェット「1. カタログ名(必須)」が空です。"
        "画面上部のウィジェットでカタログ名を入力してから再実行してください。"
    )

print(f"カタログ名             : {catalog}")
print(f"スキーマ名             : {schema}")
print(f"顧客数                 : {num_customers:,}")
print(f"商品数                 : {num_products:,}")
print(f"目標トランザクション数 : {target_num_transactions:,}")
print(f"履歴の月数             : {months_back}")
print(f"言語                   : {language}")
print(f"既存テーブルを削除     : {reset_data}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. カタログ・スキーマ・ボリュームの準備

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.workshop_files")

if reset_data:
    for tbl in ["sales_transactions", "customer_master", "product_master", "segment_targets"]:
        spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.{tbl}")
    print("Existing tables dropped.")
# Always drop segment_targets — it should be created via M2 hands-on, not by this Notebook.
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.segment_targets")

print(f"Catalog/Schema/Volume ready: {catalog}.{schema}")
print(f"Volume path               : /Volumes/{catalog}/{schema}/workshop_files")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 定数・参照データ準備
# MAGIC
# MAGIC 地域・カテゴリ・ブランド等のマスタ参照データを定義します。

# COMMAND ----------

from datetime import date, timedelta
import calendar
import random
random.seed(42)

# Date range
today = date.today()
start_year = today.year - (months_back // 12)
start_month = today.month - (months_back % 12) + 1
if start_month <= 0:
    start_month += 12
    start_year -= 1
if start_month > 12:
    start_month -= 12
    start_year += 1
start_date = date(start_year, start_month, 1)
end_date = today

print(f"Date range: {start_date} → {end_date}")

# Region → Prefecture mapping (Japanese)
REGION_PREFECTURE_JA = {
    "北海道・東北": ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
    "関東": ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"],
    "中部": ["新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県"],
    "関西": ["三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
    "中国・四国": ["鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県"],
    "九州・沖縄": ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"],
}
REGION_WEIGHTS_JA = {
    "北海道・東北": 5,
    "関東": 40,
    "中部": 15,
    "関西": 20,
    "中国・四国": 10,
    "九州・沖縄": 10,
}
REGION_TRANSLATE = {
    "北海道・東北": "North",
    "関東": "Kanto",
    "中部": "Chubu",
    "関西": "Kansai",
    "中国・四国": "ChugokuShikoku",
    "九州・沖縄": "Kyushu",
}
URBAN_REGIONS_JA = ["関東", "関西"]  # for D2

if language == "en":
    REGION_PREFECTURE_MAP = {REGION_TRANSLATE[k]: v for k, v in REGION_PREFECTURE_JA.items()}
    REGION_WEIGHTS = {REGION_TRANSLATE[k]: v for k, v in REGION_WEIGHTS_JA.items()}
    URBAN_REGIONS = [REGION_TRANSLATE[r] for r in URBAN_REGIONS_JA]
else:
    REGION_PREFECTURE_MAP = REGION_PREFECTURE_JA
    REGION_WEIGHTS = REGION_WEIGHTS_JA
    URBAN_REGIONS = URBAN_REGIONS_JA

# Categories
CATEGORIES = {
    "Apparel": ["Outerwear", "Tops", "Bottoms", "Footwear", "Accessories"],
    "Electronics": ["Smartphone", "Laptop", "Audio", "Camera", "Wearable"],
    "Home": ["Furniture", "Kitchenware", "Bedding", "Decor"],
    "Beauty": ["Skincare", "Makeup", "Haircare", "Fragrance"],
    "Food": ["Snacks", "Beverages", "Confectionery"],
}
CATEGORY_WEIGHTS = {"Apparel": 30, "Electronics": 25, "Home": 20, "Beauty": 15, "Food": 10}
# Price ranges compressed so revenue share roughly tracks transaction share (within 1.5x avg).
# Wider ranges cause Electronics to dominate revenue regardless of transaction share.
CATEGORY_PRICE_RANGE = {
    "Apparel":     (1500, 6000),
    "Electronics": (2000, 7000),
    "Home":        (1500, 5500),
    "Beauty":      (1500, 6000),
    "Food":        (1200, 4500),
}

# Brands: top 3 = 60% (F2)
BRANDS = [f"Brand{c}" for c in "ABCDEFGHIJ"]
BRAND_WEIGHTS = [25, 20, 15, 10, 8, 7, 5, 4, 3, 3]

# Customer attributes
SEGMENTS = ["Basic", "Standard", "Premium"]
SEGMENT_WEIGHTS = [60, 30, 10]
LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
AGE_GROUPS = ["10s", "20s", "30s", "40s", "50s", "60s+"]
AGE_WEIGHTS = [5, 22, 25, 23, 15, 10]
GENDERS = ["F", "M", "Other"]
GENDER_WEIGHTS = [54, 44, 2]
ACQUISITION_CHANNELS = ["Web", "Mobile", "Store", "Referral", "SNS"]
ACQUISITION_WEIGHTS = [25, 20, 25, 15, 15]

# Channels & Payment
CHANNELS = ["Online", "Store", "Mobile App"]
PAYMENT_METHODS = ["Credit", "Cash", "Mobile Pay", "QR Pay"]

# Channel preference by age (G1, G3) — calibrated so aggregate ~ Online 45 / Store 40 / Mobile 15
CHANNEL_PREF_BY_AGE = {
    "10s":  (0.20, 0.30, 0.50),
    "20s":  (0.45, 0.30, 0.25),
    "30s":  (0.55, 0.30, 0.15),
    "40s":  (0.55, 0.40, 0.05),
    "50s":  (0.40, 0.55, 0.05),
    "60s+": (0.25, 0.70, 0.05),
}

# Payment preference by age + channel (simplified — by age primarily)
PAYMENT_PREF_BY_AGE = {
    "10s":  (0.10, 0.10, 0.40, 0.40),  # Credit, Cash, Mobile, QR
    "20s":  (0.20, 0.10, 0.40, 0.30),
    "30s":  (0.40, 0.10, 0.30, 0.20),
    "40s":  (0.55, 0.15, 0.20, 0.10),
    "50s":  (0.60, 0.25, 0.10, 0.05),
    "60s+": (0.55, 0.40, 0.03, 0.02),
}

# Category preference by (age_group, gender) — C1, C3
# Order: Apparel, Electronics, Home, Beauty, Food
# Calibrated so aggregate transaction share ~ 30 / 25 / 20 / 15 / 10
# (Previous values aggregated to ~25/19/22/22/12; scaled to shift toward target.)
CATEGORY_PREF = {
    ("10s", "F"):   (43, 12,  4, 33,  7),
    ("10s", "M"):   (31, 43,  9,  8, 15),
    ("20s", "F"):   (43, 12,  9, 29,  7),
    ("20s", "M"):   (31, 37, 13,  8, 15),
    ("30s", "F"):   (37, 18, 17, 21,  7),
    ("30s", "M"):   (31, 37, 22,  8,  7),
    ("40s", "F"):   (31, 18, 22, 16, 11),
    ("40s", "M"):   (24, 37, 26,  8,  7),
    ("50s", "F"):   (24, 18, 26, 16, 11),
    ("50s", "M"):   (18, 31, 30,  8, 11),
    ("60s+", "F"):  (18, 18, 30, 12, 15),
    ("60s+", "M"):  (18, 25, 30,  8, 15),
}
# For "Other" gender, average F and M weights
for ag in AGE_GROUPS:
    f_w = CATEGORY_PREF[(ag, "F")]
    m_w = CATEGORY_PREF[(ag, "M")]
    CATEGORY_PREF[(ag, "Other")] = tuple((f + m) / 2 for f, m in zip(f_w, m_w))

# Names
FAMILY_JA = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
             "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"]
GIVEN_JA_F = ["美咲", "結衣", "七海", "葵", "さくら", "結菜", "美桜", "心愛", "凛", "莉子",
              "陽菜", "彩", "美月", "ひな", "杏", "愛美", "千尋", "舞", "桃花", "由香"]
GIVEN_JA_M = ["翔", "健太", "大輝", "拓海", "達也", "翔太", "直樹", "雄太", "颯太", "陽斗",
              "蓮", "湊", "悠斗", "陸", "大和", "蒼", "悠", "樹", "颯", "誠"]
FAMILY_EN = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
             "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
             "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
GIVEN_EN_F = ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan",
              "Jessica", "Sarah", "Karen", "Emily", "Lisa", "Anna", "Margaret", "Betty"]
GIVEN_EN_M = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
              "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark"]

print("Constants loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `customer_master` の生成
# MAGIC
# MAGIC **埋め込み傾向**:
# MAGIC - B1: セグメント分布 Basic 60% / Standard 30% / Premium 10%
# MAGIC - C2: 性別比 F 54% / M 44% / Other 2%
# MAGIC - D1: 地域別シェア 関東 40% / 関西 20% / その他
# MAGIC - D2: 都市部(関東・関西)の Premium 比率を高める
# MAGIC - E1: ロイヤリティ Bronze 50% / Silver 30% / Gold 15% / Platinum 5%(セグメントと相関)
# MAGIC - E3: 取得チャネル × 年齢(SNS は若年中心、Store は高齢中心)
# MAGIC - E4: Referral 経由はロイヤリティが上がりやすい

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType, DecimalType
from pyspark.sql import Row

# Categorical assignment from a materialized random column.
# CRITICAL: rand value MUST be materialized into a column BEFORE building the CASE WHEN.
# Passing F.rand() directly into .when() causes it to be re-evaluated per condition,
# producing nonsense distributions (e.g. 30s 36% / 60s+ 1% instead of weighted spec).
# Similarly, dbldatagen's chained `random=True` shared an RNG stream and forced strong
# attribute correlations (10s-30s all F, 50s+ all M).
def assign_categorical(df, target_col, rand_col_name, values, weights):
    total = float(sum(weights))
    cum = 0.0
    expr = None
    last_idx = len(values) - 1
    for i, (v, w) in enumerate(zip(values, weights)):
        cum += w
        if i == last_idx:
            cond = F.lit(True)
        else:
            cond = F.col(rand_col_name) < (cum / total)
        if expr is None:
            expr = F.when(cond, F.lit(v))
        else:
            expr = expr.when(cond, F.lit(v))
    return df.withColumn(target_col, expr)

# Base sequence 1..N, materialize all rand columns up front to lock values
customer_base = (
    spark.range(1, num_customers + 1)
    .withColumnRenamed("id", "seq_id")
    .withColumn("seq_id", F.col("seq_id").cast("int"))
    .withColumn("_age_rnd", F.rand(seed=151))
    .withColumn("_gen_rnd", F.rand(seed=152))
    .withColumn("_reg_rnd", F.rand(seed=153))
    .withColumn("_sig_rnd", F.rand(seed=154))
)
customer_base = assign_categorical(customer_base, "age_group", "_age_rnd", AGE_GROUPS, AGE_WEIGHTS)
customer_base = assign_categorical(customer_base, "gender", "_gen_rnd", GENDERS, GENDER_WEIGHTS)
customer_base = assign_categorical(customer_base, "region", "_reg_rnd",
                                   list(REGION_WEIGHTS.keys()),
                                   list(REGION_WEIGHTS.values()))
customer_base = customer_base.withColumn(
    "signup_date_raw",
    F.expr(f"date_sub(date('{today}'), cast(_sig_rnd * {5*365} as int))")
).drop("_age_rnd", "_gen_rnd", "_reg_rnd", "_sig_rnd")

# Post-processing: customer_id, segment (with D2 urban bias), prefecture, loyalty_tier (with E correlation),
# acquisition_channel (with E3 age correlation), name (language-aware)
from pyspark.sql.window import Window

# customer_id
customer_with_id = customer_base.withColumn(
    "customer_id", F.format_string("C%05d", F.col("seq_id"))
)

# segment with urban bias (D2): urban Premium ratio +5pt
urban_list = URBAN_REGIONS
customer_with_segment = customer_with_id.withColumn(
    "_seg_rnd", F.rand(seed=101)
).withColumn(
    "segment",
    F.when(F.col("region").isin(urban_list),
           F.when(F.col("_seg_rnd") < 0.55, "Basic")
            .when(F.col("_seg_rnd") < 0.85, "Standard")
            .otherwise("Premium"))
    .otherwise(
           F.when(F.col("_seg_rnd") < 0.63, "Basic")
            .when(F.col("_seg_rnd") < 0.93, "Standard")
            .otherwise("Premium"))
)

# acquisition_channel with age correlation (E3)
customer_with_acq = customer_with_segment.withColumn(
    "_acq_rnd", F.rand(seed=102)
).withColumn(
    "acquisition_channel",
    # 10s/20s: SNS+Mobile heavy
    F.when(F.col("age_group").isin("10s", "20s"),
           F.when(F.col("_acq_rnd") < 0.35, "SNS")
            .when(F.col("_acq_rnd") < 0.65, "Mobile")
            .when(F.col("_acq_rnd") < 0.80, "Web")
            .when(F.col("_acq_rnd") < 0.90, "Referral")
            .otherwise("Store"))
    # 30s/40s: Web+Mobile
    .when(F.col("age_group").isin("30s", "40s"),
           F.when(F.col("_acq_rnd") < 0.35, "Web")
            .when(F.col("_acq_rnd") < 0.60, "Mobile")
            .when(F.col("_acq_rnd") < 0.75, "Referral")
            .when(F.col("_acq_rnd") < 0.90, "Store")
            .otherwise("SNS"))
    # 50s+: Store heavy
    .otherwise(
           F.when(F.col("_acq_rnd") < 0.45, "Store")
            .when(F.col("_acq_rnd") < 0.70, "Web")
            .when(F.col("_acq_rnd") < 0.85, "Referral")
            .when(F.col("_acq_rnd") < 0.95, "Mobile")
            .otherwise("SNS"))
)

# loyalty_tier — correlated with segment (E1 base + segment correlation) and Referral boost (E4)
customer_with_loyalty = customer_with_acq.withColumn(
    "_loy_rnd", F.rand(seed=103)
).withColumn(
    "_loy_adj_rnd",
    F.when(F.col("acquisition_channel") == "Referral", F.col("_loy_rnd") + 0.20)
     .otherwise(F.col("_loy_rnd"))
).withColumn(
    "loyalty_tier",
    F.when(F.col("segment") == "Premium",
           F.when(F.col("_loy_adj_rnd") < 0.10, "Bronze")
            .when(F.col("_loy_adj_rnd") < 0.30, "Silver")
            .when(F.col("_loy_adj_rnd") < 0.65, "Gold")
            .otherwise("Platinum"))
    .when(F.col("segment") == "Standard",
           F.when(F.col("_loy_adj_rnd") < 0.35, "Bronze")
            .when(F.col("_loy_adj_rnd") < 0.70, "Silver")
            .when(F.col("_loy_adj_rnd") < 0.92, "Gold")
            .otherwise("Platinum"))
    .otherwise(  # Basic
           F.when(F.col("_loy_adj_rnd") < 0.65, "Bronze")
            .when(F.col("_loy_adj_rnd") < 0.88, "Silver")
            .when(F.col("_loy_adj_rnd") < 0.98, "Gold")
            .otherwise("Platinum"))
)

# prefecture (random within region)
# Build a small reference DF
prefecture_rows = []
for r, prefs in REGION_PREFECTURE_MAP.items():
    for p in prefs:
        prefecture_rows.append(Row(region=r, prefecture=p))
prefecture_df = spark.createDataFrame(prefecture_rows)
# Add a random selection within region
# Approach: for each region, generate a hash-based index
customer_with_pref_rnd = customer_with_loyalty.withColumn("_pref_rnd", F.rand(seed=104))
# Join with prefecture_df via region + bucket
# Simpler: For each customer, pick a random prefecture from the region
# Use a window over region with row_number on a randomized order
# Even simpler approach: encode prefecture_df with index per region, then use modulo

w_pref = Window.partitionBy("region").orderBy("prefecture")
prefecture_indexed = prefecture_df.withColumn("pref_idx", F.row_number().over(w_pref) - 1)
prefecture_counts = prefecture_indexed.groupBy("region").agg(F.count("*").alias("pref_count"))

customer_with_pref_join = (
    customer_with_pref_rnd.join(prefecture_counts, "region")
    .withColumn("pick_idx", (F.col("_pref_rnd") * F.col("pref_count")).cast("int"))
    .join(prefecture_indexed, ["region"])
    .filter(F.col("pref_idx") == F.col("pick_idx"))
    .drop("pref_idx", "pref_count", "pick_idx")
)

# customer_name
if language == "ja":
    family_list = FAMILY_JA
    given_f_list = GIVEN_JA_F
    given_m_list = GIVEN_JA_M
    separator = " "
else:
    family_list = FAMILY_EN
    given_f_list = GIVEN_EN_F
    given_m_list = GIVEN_EN_M
    separator = " "

family_array = F.array(*[F.lit(x) for x in family_list])
given_f_array = F.array(*[F.lit(x) for x in given_f_list])
given_m_array = F.array(*[F.lit(x) for x in given_m_list])

customer_with_name = customer_with_pref_join.withColumn(
    "_fam_idx", (F.rand(seed=105) * len(family_list)).cast("int")
).withColumn(
    "_giv_idx_f", (F.rand(seed=106) * len(given_f_list)).cast("int")
).withColumn(
    "_giv_idx_m", (F.rand(seed=107) * len(given_m_list)).cast("int")
).withColumn(
    "_family", family_array[F.col("_fam_idx")]
).withColumn(
    "_given",
    F.when(F.col("gender") == "F", given_f_array[F.col("_giv_idx_f")])
     .when(F.col("gender") == "M", given_m_array[F.col("_giv_idx_m")])
     .otherwise(given_f_array[F.col("_giv_idx_f")])  # Other → use F list
).withColumn(
    "customer_name",
    F.concat(F.col("_family"), F.lit(separator), F.col("_given"))
)

# signup_date with recency bias — recent signups more frequent
# Approximate by overriding signup_date_raw with a quadratic distribution
# Use rand^2 to push toward newer dates (and shift to within 5 years range)
customer_with_signup = customer_with_name.withColumn(
    "_sd_rnd", F.pow(F.rand(seed=108), F.lit(0.5))  # 0..1 with bias toward 1
).withColumn(
    "signup_date",
    F.expr(f"date_sub(date('{today}'), cast((1 - _sd_rnd) * {5*365} as int))")
)

# Final customer_master
customer_master_df = customer_with_signup.select(
    "customer_id",
    "customer_name",
    "age_group",
    "gender",
    "region",
    "prefecture",
    "segment",
    "signup_date",
    "acquisition_channel",
    "loyalty_tier",
)

# Write to UC
(customer_master_df.write
 .mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(f"{catalog}.{schema}.customer_master"))

print(f"Wrote customer_master: {customer_master_df.count():,} rows")
display(customer_master_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. `product_master` の生成
# MAGIC
# MAGIC **埋め込み傾向**:
# MAGIC - F1: カテゴリ別売上構成(Apparel 30% / Electronics 25% / Home 20% / Beauty 15% / Food 10%) — 商品数の分布で表現
# MAGIC - F2: 上位 3 ブランド 60% シェア
# MAGIC - F4: 価格帯はカテゴリで異なる(Electronics は高め、Food は低め)
# MAGIC - launch_date: 過去 5 年間、20% が直近 6 ヶ月以内

# COMMAND ----------

# Generate product master with materialized rand columns
product_base = (
    spark.range(1, num_products + 1)
    .withColumnRenamed("id", "seq_id")
    .withColumn("seq_id", F.col("seq_id").cast("int"))
    .withColumn("_cat_rnd", F.rand(seed=251))
    .withColumn("_brand_rnd", F.rand(seed=252))
)
product_base = assign_categorical(product_base, "category", "_cat_rnd",
                                  list(CATEGORY_WEIGHTS.keys()),
                                  list(CATEGORY_WEIGHTS.values()))
product_base = assign_categorical(product_base, "brand", "_brand_rnd", BRANDS, BRAND_WEIGHTS)
product_base = product_base.drop("_cat_rnd", "_brand_rnd")

# sub_category: pick from category-specific list
sub_cat_rows = []
for cat, subs in CATEGORIES.items():
    for s in subs:
        sub_cat_rows.append(Row(category=cat, sub_category=s))
sub_cat_df = spark.createDataFrame(sub_cat_rows)

w_sub = Window.partitionBy("category").orderBy("sub_category")
sub_cat_indexed = sub_cat_df.withColumn("sub_idx", F.row_number().over(w_sub) - 1)
sub_cat_counts = sub_cat_indexed.groupBy("category").agg(F.count("*").alias("sub_count"))

product_with_sub = (
    product_base.withColumn("_sub_rnd", F.rand(seed=201))
    .join(sub_cat_counts, "category")
    .withColumn("pick_idx", (F.col("_sub_rnd") * F.col("sub_count")).cast("int"))
    .join(sub_cat_indexed, ["category"])
    .filter(F.col("sub_idx") == F.col("pick_idx"))
    .drop("sub_idx", "sub_count", "pick_idx", "_sub_rnd")
)

# list_price: per category
price_lookup_rows = []
for cat, (low, high) in CATEGORY_PRICE_RANGE.items():
    price_lookup_rows.append(Row(category=cat, price_low=low, price_high=high))
price_lookup_df = spark.createDataFrame(price_lookup_rows)

product_with_price = (
    product_with_sub.join(price_lookup_df, "category")
    .withColumn("_price_rnd", F.rand(seed=202))
    .withColumn(
        "list_price",
        # log-normal-ish: bias toward lower end
        F.round(
            F.col("price_low") + F.pow(F.col("_price_rnd"), F.lit(2.0)) * (F.col("price_high") - F.col("price_low")),
            -2,  # round to 100
        ).cast("decimal(10,2)")
    )
    .drop("price_low", "price_high", "_price_rnd")
)

# launch_date: 20% within last 6 months, 80% in past 5 years
product_with_launch = product_with_price.withColumn(
    "_launch_pick", F.rand(seed=203)
).withColumn(
    "launch_date",
    F.when(F.col("_launch_pick") < 0.20,
           # last 6 months
           F.expr(f"date_sub(date('{today}'), cast(rand() * 180 as int))"))
    .otherwise(
           F.expr(f"date_sub(date('{today}'), cast(180 + rand() * (5*365 - 180) as int))"))
)

# product_id and product_name
product_with_id = product_with_launch.withColumn(
    "product_id", F.format_string("P%04d", F.col("seq_id"))
)

# product_name: {brand} {sub_category} {sequence-suffix}
product_master_df = product_with_id.withColumn(
    "product_name",
    F.concat(F.col("brand"), F.lit(" "), F.col("sub_category"), F.lit(" "), F.lpad(F.col("seq_id").cast("string"), 4, "0"))
).select(
    "product_id",
    "product_name",
    "category",
    "sub_category",
    "brand",
    "list_price",
    "launch_date",
)

(product_master_df.write
 .mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(f"{catalog}.{schema}.product_master"))

print(f"Wrote product_master: {product_master_df.count():,} rows")
display(product_master_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. `sales_transactions` の生成
# MAGIC
# MAGIC **埋め込み傾向**:
# MAGIC - A1: 24 ヶ月で年率 +10% 成長
# MAGIC - A2-A4: 12月 +30% / 3月 +15% / 7-8月 +20%
# MAGIC - A5: 土日 +30%
# MAGIC - A6: 月末3日 +15%
# MAGIC - B2: Premium 約 15,000円 / Standard 約 8,000円 / Basic 約 3,500円
# MAGIC - B3: Premium 月3回以上 / Standard 月1.5回 / Basic 月0.5回
# MAGIC - C1: 年齢 × カテゴリ(20-30代女性は Beauty/Apparel、40-50代男性は Electronics/Home)
# MAGIC - C3: 性別 × カテゴリ(女性は Beauty/Apparel、男性は Electronics)
# MAGIC - F3: 直近 6ヶ月内 launch の商品が売上の約 25%
# MAGIC - G1: Online 45% / Store 40% / Mobile App 15%
# MAGIC - G3: 決済手段 × 世代
# MAGIC - H1: 通常 30% 割引、6/12月は 60%

# COMMAND ----------

# Strategy:
# 1. For each customer, compute target transaction count based on segment (B3)
# 2. Expand customers to have N rows each
# 3. For each transaction, determine: target category (C1/C3), product, date (A), channel (G), payment (G3), quantity, discount

customer_for_trans = spark.table(f"{catalog}.{schema}.customer_master")
product_for_trans = spark.table(f"{catalog}.{schema}.product_master")

# Step 1: Target transaction count per customer
# Premium: avg ~30 trans (12.5 trans/year over 24mo) — wait, we want 50k total
# Calc: Premium = 30, Standard = 13, Basic = 5
# 500 * 30 + 1500 * 13 + 3000 * 5 = 15000 + 19500 + 15000 = 49500 ≈ 50k
# Scale by target_num_transactions / 50000
SCALE = target_num_transactions / 50000.0

customer_with_n = customer_for_trans.withColumn(
    "_n_rnd", F.rand(seed=301)
).withColumn(
    "_n_base",
    # B3: Premium ~6× Basic, Standard ~3× Basic (per-month freq ratio 3 / 1.5 / 0.5)
    F.when(F.col("segment") == "Premium", F.lit(30 * SCALE))
     .when(F.col("segment") == "Standard", F.lit(15 * SCALE))
     .otherwise(F.lit(5 * SCALE))
).withColumn(
    "n_transactions",
    F.greatest(
        F.lit(0),
        F.round(F.col("_n_base") + (F.col("_n_rnd") - 0.5) * F.col("_n_base") * 0.6).cast("int")
    )
)

# Explode: one row per intended transaction
transactions_base = (
    customer_with_n
    .withColumn("trans_seq", F.explode(F.sequence(F.lit(1), F.col("n_transactions"))))
    .select("customer_id", "age_group", "gender", "region", "segment", "loyalty_tier", "trans_seq")
)
print(f"Generated base transaction count: {transactions_base.count():,}")

# COMMAND ----------

# Step 2: Determine target category per transaction (C1, C3)
# Build category preference DF with prefixed columns to avoid ambiguity
cat_pref_rows = []
for (age, gender), weights in CATEGORY_PREF.items():
    total = sum(weights)
    cum = 0
    for cat, w in zip(CATEGORIES.keys(), weights):
        prev_cum = cum
        cum += w
        cat_pref_rows.append(Row(
            cp_age_group=age, cp_gender=gender, cp_category=cat,
            cp_prev_prob=float(prev_cum / total), cp_cum_prob=float(cum / total)
        ))
cat_pref_df = spark.createDataFrame(cat_pref_rows)

transactions_with_cat = (
    transactions_base.withColumn("_cat_rnd", F.rand(seed=302))
    .join(F.broadcast(cat_pref_df),
          (F.col("age_group") == F.col("cp_age_group")) &
          (F.col("gender") == F.col("cp_gender")) &
          (F.col("_cat_rnd") >= F.col("cp_prev_prob")) &
          (F.col("_cat_rnd") < F.col("cp_cum_prob")),
          "left")
    .drop("cp_age_group", "cp_gender", "cp_prev_prob", "cp_cum_prob")
    .withColumnRenamed("cp_category", "target_category")
)

# COMMAND ----------

# Step 3: Sample product within target category, biased by F3 (new product effect) and F2 (brand concentration)
# Pre-compute product cumulative weights within category
product_weighted = product_for_trans.withColumn(
    "_is_new", (F.col("launch_date") >= F.date_sub(F.lit(str(today)), 180)).cast("int")
).withColumn(
    "product_weight",
    # F3: ~25% new product share. With 20% products being "new", weight 1.33 → ~25% share.
    # (3x previously gave ~45%, way too high.)
    F.when(F.col("_is_new") == 1, F.lit(1.33))
     .otherwise(F.lit(1.0))
)

w_pcat = Window.partitionBy("category")
w_pcat_o = Window.partitionBy("category").orderBy("product_id").rowsBetween(Window.unboundedPreceding, 0)

product_with_cumprob = (
    product_weighted
    .withColumn("total_w", F.sum("product_weight").over(w_pcat))
    .withColumn("cum_w", F.sum("product_weight").over(w_pcat_o))
    .withColumn("p_cum_prob", F.col("cum_w") / F.col("total_w"))
    .withColumn("p_prev_prob", (F.col("cum_w") - F.col("product_weight")) / F.col("total_w"))
    .select("product_id",
            F.col("category").alias("p_category"),
            "list_price",
            "p_prev_prob",
            "p_cum_prob")
)

transactions_with_product = (
    transactions_with_cat.withColumn("_prod_rnd", F.rand(seed=303))
    .join(
        F.broadcast(product_with_cumprob),
        (F.col("target_category") == F.col("p_category")) &
        (F.col("_prod_rnd") >= F.col("p_prev_prob")) &
        (F.col("_prod_rnd") < F.col("p_cum_prob")),
        "left"
    )
    .drop("p_prev_prob", "p_cum_prob", "p_category")
)

# COMMAND ----------

# Step 4: Determine transaction_date with seasonal/weekly/monthly weights (A1-A6)
# Build a date-weight lookup
import calendar as _cal

all_dates = []
d = start_date
while d <= end_date:
    weight = 1.0
    # A1: monthly growth +10% annual
    months_from_start = (d.year - start_date.year) * 12 + (d.month - start_date.month)
    weight *= (1.0 + 0.10 / 12 * months_from_start)
    # A2: December +30%
    if d.month == 12:
        weight *= 1.30
    elif d.month == 3:
        weight *= 1.15  # A3
    elif d.month in (7, 8):
        weight *= 1.20  # A4
    # A5: weekend
    if d.weekday() in (5, 6):
        weight *= 1.30
    # A6: month-end last 3 days
    last_day = _cal.monthrange(d.year, d.month)[1]
    if d.day >= last_day - 2:
        weight *= 1.15
    all_dates.append((d, weight))
    d += timedelta(days=1)

# Compute cumulative weights
total_w = sum(w for _, w in all_dates)
cum = 0
date_rows = []
for dt, w in all_dates:
    prev = cum
    cum += w
    date_rows.append(Row(d_transaction_date=dt, d_prev_prob=float(prev/total_w), d_cum_prob=float(cum/total_w)))

date_lookup_df = spark.createDataFrame(date_rows)

# Sample date per transaction with broadcast join
transactions_with_date = (
    transactions_with_product.withColumn("_date_rnd", F.rand(seed=304))
    .join(F.broadcast(date_lookup_df),
          (F.col("_date_rnd") >= F.col("d_prev_prob")) & (F.col("_date_rnd") < F.col("d_cum_prob")))
    .drop("d_prev_prob", "d_cum_prob", "_date_rnd")
    .withColumnRenamed("d_transaction_date", "transaction_date")
)

# COMMAND ----------

# Step 5: Channel (G1, channel by age) — use ch_ prefix to avoid ambiguity
channel_pref_rows = []
for age, (online, store, mobile) in CHANNEL_PREF_BY_AGE.items():
    channel_pref_rows.append(Row(ch_age_group=age, ch_channel="Online", ch_prev=0.0, ch_cum=float(online)))
    channel_pref_rows.append(Row(ch_age_group=age, ch_channel="Store", ch_prev=float(online), ch_cum=float(online + store)))
    channel_pref_rows.append(Row(ch_age_group=age, ch_channel="Mobile App", ch_prev=float(online + store), ch_cum=float(online + store + mobile)))
channel_pref_df = spark.createDataFrame(channel_pref_rows)

transactions_with_channel = (
    transactions_with_date.withColumn("_chan_rnd", F.rand(seed=305))
    .join(F.broadcast(channel_pref_df),
          (F.col("age_group") == F.col("ch_age_group")) &
          (F.col("_chan_rnd") >= F.col("ch_prev")) &
          (F.col("_chan_rnd") < F.col("ch_cum")),
          "left")
    .drop("ch_age_group", "ch_prev", "ch_cum", "_chan_rnd")
    .withColumnRenamed("ch_channel", "channel")
)

# Payment (G3) — use py_ prefix
payment_pref_rows = []
for age, (cr, ca, mo, qr) in PAYMENT_PREF_BY_AGE.items():
    payment_pref_rows.append(Row(py_age_group=age, py_method="Credit", py_prev=0.0, py_cum=float(cr)))
    payment_pref_rows.append(Row(py_age_group=age, py_method="Cash", py_prev=float(cr), py_cum=float(cr + ca)))
    payment_pref_rows.append(Row(py_age_group=age, py_method="Mobile Pay", py_prev=float(cr + ca), py_cum=float(cr + ca + mo)))
    payment_pref_rows.append(Row(py_age_group=age, py_method="QR Pay", py_prev=float(cr + ca + mo), py_cum=float(cr + ca + mo + qr)))
payment_pref_df = spark.createDataFrame(payment_pref_rows)

transactions_with_payment = (
    transactions_with_channel.withColumn("_pay_rnd", F.rand(seed=306))
    .join(F.broadcast(payment_pref_df),
          (F.col("age_group") == F.col("py_age_group")) &
          (F.col("_pay_rnd") >= F.col("py_prev")) &
          (F.col("_pay_rnd") < F.col("py_cum")),
          "left")
    .drop("py_age_group", "py_prev", "py_cum", "_pay_rnd")
    .withColumnRenamed("py_method", "payment_method")
)

# COMMAND ----------

# Step 6: quantity, discount, amount
# Quantity varies by segment so per-transaction amount differs (B2):
#   Premium avg ~5 units, Standard ~3, Basic ~1.5
# Combined with avg unit_price ~3K, hits target avg amount Premium 15K / Std 9K / Basic 4.5K.
transactions_with_qty = transactions_with_payment.withColumn(
    "_qty_rnd", F.rand(seed=307)
).withColumn(
    "_qty_base",
    F.when(F.col("segment") == "Premium", F.lit(5.0))
     .when(F.col("segment") == "Standard", F.lit(3.0))
     .otherwise(F.lit(1.5))
).withColumn(
    "quantity",
    F.greatest(
        F.lit(1),
        F.round(F.col("_qty_base") + (F.col("_qty_rnd") - 0.5) * F.col("_qty_base") * 0.6).cast("int")
    )
)

# Discount: H1 — 30% normal, 60% during sale months (June, December)
# H2 — Basic +50% sensitivity (i.e., higher discount rate for Basic during sale months)
transactions_with_discount_flag = transactions_with_qty.withColumn(
    "_disc_rnd", F.rand(seed=308)
).withColumn(
    "_sale_month",
    F.when(F.month(F.col("transaction_date")).isin(6, 12), F.lit(1)).otherwise(F.lit(0))
).withColumn(
    "_disc_threshold",
    F.when(F.col("_sale_month") == 1,
           F.when(F.col("segment") == "Basic", F.lit(0.75))
            .otherwise(F.lit(0.60)))
    .otherwise(
           F.when(F.col("segment") == "Basic", F.lit(0.40))
            .otherwise(F.lit(0.30)))
).withColumn(
    "has_discount", (F.col("_disc_rnd") < F.col("_disc_threshold")).cast("int")
)

# Discount amount: 10-30% of list_price * quantity when applied
transactions_with_amount = transactions_with_discount_flag.withColumn(
    "_disc_pct_rnd", F.rand(seed=309)
).withColumn(
    "_subtotal", F.col("list_price") * F.col("quantity")
).withColumn(
    "discount_amount",
    F.when(F.col("has_discount") == 1,
           F.round(F.col("_subtotal") * (F.lit(0.10) + F.col("_disc_pct_rnd") * F.lit(0.20)), -1))
    .otherwise(F.lit(0.0))
    .cast("decimal(12,2)")
).withColumn(
    "amount",
    F.round(F.col("_subtotal") - F.col("discount_amount"), 2).cast("decimal(12,2)")
)

# transaction_id; rename FK columns to avoid name collision with dimension PKs after join in Lakeflow Designer.
transactions_final = transactions_with_amount.withColumn(
    "_trans_seq",
    F.row_number().over(Window.orderBy("customer_id", "transaction_date", "trans_seq"))
).withColumn(
    "transaction_id", F.format_string("T%08d", F.col("_trans_seq"))
).withColumnRenamed("customer_id", "cust_id") \
 .withColumnRenamed("product_id", "prod_id") \
 .select(
    "transaction_id",
    "cust_id",        # FK → customer_master.customer_id (renamed to avoid join-output collision)
    "prod_id",        # FK → product_master.product_id (renamed to avoid join-output collision)
    "transaction_date",
    "quantity",
    "amount",
    "discount_amount",
    "channel",
    "payment_method",
).filter(F.col("prod_id").isNotNull())  # safety: drop any orphans

# Write
(transactions_final.write
 .mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(f"{catalog}.{schema}.sales_transactions"))

actual_count = transactions_final.count()
print(f"Wrote sales_transactions: {actual_count:,} rows (target was {target_num_transactions:,})")
display(transactions_final.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. `segment_targets.xlsx` の生成(UC Volume へ出力)
# MAGIC
# MAGIC **埋め込み傾向**:
# MAGIC - I1: 月 × セグメント で 85〜110% に達成率分布
# MAGIC - I2: Premium はほぼ達成、Basic は未達月あり
# MAGIC - I3: 年末・年度末は全達成、平月は未達気味

# COMMAND ----------

# Compute actual revenue per segment per month, then set target as 90-105% of actual (so achievement is 95-110%)
actual_monthly = spark.sql(f"""
    SELECT
        c.segment,
        date_trunc('MONTH', t.transaction_date) AS month_start,
        SUM(t.amount) AS actual_amount,
        COUNT(*) AS actual_orders
    FROM {catalog}.{schema}.sales_transactions t
    JOIN {catalog}.{schema}.customer_master c ON t.cust_id = c.customer_id
    GROUP BY c.segment, date_trunc('MONTH', t.transaction_date)
    ORDER BY month_start, segment
""")

import math

actual_rows = actual_monthly.collect()
targets_data = []
random.seed(1234)
for r in actual_rows:
    seg = r["segment"]
    month = r["month_start"].date()
    actual_amt = float(r["actual_amount"])
    actual_orders = int(r["actual_orders"])
    is_year_end = (month.month in (3, 12))
    # Achievement target distribution
    if seg == "Premium":
        # I2: Premium ほぼ達成 (~100-110%)
        ach = random.uniform(0.95, 1.10)
    elif seg == "Standard":
        ach = random.uniform(0.92, 1.05)
    else:  # Basic — I2: 未達月あり, I3: 年末・年度末は達成
        if is_year_end:
            ach = random.uniform(0.95, 1.05)
        else:
            ach = random.uniform(0.85, 1.02)  # 85-102%, half-ish miss
    target_amt = round(actual_amt / ach, -3)  # round to thousands
    target_ord = max(1, round(actual_orders / ach))
    targets_data.append((seg, month, target_amt, target_ord))

# Sort by month, segment
targets_data.sort(key=lambda x: (x[1], x[0]))

# Create Spark DataFrame (use inferred schema, then cast)
targets_df = (
    spark.createDataFrame(
        [(s, m, float(a), int(o)) for s, m, a, o in targets_data],
        schema=["segment", "month", "target_amount", "target_order_count"]
    )
    .withColumn("target_amount", F.col("target_amount").cast("decimal(14,2)"))
)

# Note: segment_targets は Delta テーブルとしては保存しない。
# Module 2 のハンズオンで参加者が「ソース → ファイルからテーブルを作成」フローを使って
# UC テーブル `segment_targets` を新規作成するため、ここで作ると名前競合する。
# 念のため既存テーブルを削除(過去ランで作成済みの可能性に備えて)
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.segment_targets")
print(f"segment_targets target preview ({targets_df.count()} rows, Excel として出力):")
display(targets_df.limit(10))

# COMMAND ----------

# Export as Excel to UC Volume
import openpyxl
from openpyxl import Workbook

volume_path = f"/Volumes/{catalog}/{schema}/workshop_files"
excel_path = f"{volume_path}/segment_targets.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "Segment Targets"
# Header — use "segment_name" instead of "segment" so M2 join output doesn't have duplicate column name
ws.append(["segment_name", "month", "target_amount", "target_order_count"])
# Data
for s, m, a, o in targets_data:
    ws.append([s, m.isoformat(), float(a), int(o)])

# Save to in-memory buffer, then write bytes to UC Volume
import io, os
if os.path.exists(excel_path):
    os.remove(excel_path)
buf = io.BytesIO()
wb.save(buf)
with open(excel_path, "wb") as f:
    f.write(buf.getvalue())
print(f"Excel exported to: {excel_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. 検証クエリ
# MAGIC
# MAGIC 埋め込んだ傾向が想定通りか確認します。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.1 件数確認

# COMMAND ----------

for tbl in ["customer_master", "product_master", "sales_transactions"]:
    cnt = spark.table(f"{catalog}.{schema}.{tbl}").count()
    print(f"{tbl:25s}: {cnt:>10,} rows")
print(f"{'segment_targets.xlsx':25s}: {len(targets_data):>10,} rows (Excel file only, no UC table)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.2 セグメント分布(B1: 期待値 Basic 60% / Standard 30% / Premium 10%)

# COMMAND ----------

display(spark.sql(f"""
    SELECT segment, COUNT(*) AS cnt,
           ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM {catalog}.{schema}.customer_master
    GROUP BY segment
    ORDER BY cnt DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.3 地域分布(D1: 関東 40% / 関西 20% / その他)

# COMMAND ----------

display(spark.sql(f"""
    SELECT region, COUNT(*) AS cnt,
           ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM {catalog}.{schema}.customer_master
    GROUP BY region
    ORDER BY cnt DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.4 月次売上トレンド(A1-A4: 成長 + 季節性)

# COMMAND ----------

display(spark.sql(f"""
    SELECT date_trunc('MONTH', transaction_date) AS month,
           ROUND(SUM(amount), 0) AS revenue,
           COUNT(*) AS num_transactions
    FROM {catalog}.{schema}.sales_transactions
    GROUP BY date_trunc('MONTH', transaction_date)
    ORDER BY month
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.5 カテゴリ別売上(F1: Apparel 30% / Electronics 25% / ...)

# COMMAND ----------

display(spark.sql(f"""
    SELECT p.category,
           ROUND(SUM(t.amount), 0) AS revenue,
           ROUND(SUM(t.amount) * 100.0 / SUM(SUM(t.amount)) OVER (), 1) AS pct
    FROM {catalog}.{schema}.sales_transactions t
    JOIN {catalog}.{schema}.product_master p ON t.prod_id = p.product_id
    GROUP BY p.category
    ORDER BY revenue DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.6 チャネル別売上(G1: Online 45% / Store 40% / Mobile App 15%)

# COMMAND ----------

display(spark.sql(f"""
    SELECT channel,
           COUNT(*) AS num_trans,
           ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct,
           ROUND(SUM(amount), 0) AS revenue
    FROM {catalog}.{schema}.sales_transactions
    GROUP BY channel
    ORDER BY num_trans DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.7 セグメント別客単価(B2: Premium 15K / Standard 8K / Basic 3.5K)

# COMMAND ----------

display(spark.sql(f"""
    SELECT c.segment,
           ROUND(AVG(t.amount), 0) AS avg_amount,
           COUNT(*) AS num_trans,
           COUNT(DISTINCT c.customer_id) AS num_customers,
           ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT c.customer_id), 2) AS trans_per_customer
    FROM {catalog}.{schema}.sales_transactions t
    JOIN {catalog}.{schema}.customer_master c ON t.cust_id = c.customer_id
    GROUP BY c.segment
    ORDER BY avg_amount DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.8 年齢 × カテゴリ(C1: 20-30代女性は Beauty/Apparel)

# COMMAND ----------

display(spark.sql(f"""
    SELECT c.age_group, c.gender, p.category,
           COUNT(*) AS num_trans
    FROM {catalog}.{schema}.sales_transactions t
    JOIN {catalog}.{schema}.customer_master c ON t.cust_id = c.customer_id
    JOIN {catalog}.{schema}.product_master p ON t.prod_id = p.product_id
    WHERE c.gender IN ('F', 'M') AND c.age_group IN ('20s', '30s', '40s', '50s')
    GROUP BY c.age_group, c.gender, p.category
    ORDER BY c.age_group, c.gender, num_trans DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9.9 新商品売上比率(F3: 直近6ヶ月内 launch が約 25%)

# COMMAND ----------

display(spark.sql(f"""
    SELECT
        CASE WHEN p.launch_date >= date_sub(current_date(), 180) THEN 'New (last 6mo)'
             ELSE 'Existing' END AS product_age,
        ROUND(SUM(t.amount), 0) AS revenue,
        ROUND(SUM(t.amount) * 100.0 / SUM(SUM(t.amount)) OVER (), 1) AS pct
    FROM {catalog}.{schema}.sales_transactions t
    JOIN {catalog}.{schema}.product_master p ON t.prod_id = p.product_id
    GROUP BY product_age
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. 完了
# MAGIC
# MAGIC データセットの生成が完了しました。
# MAGIC
# MAGIC ### 次のステップ
# MAGIC - **Catalog Explorer**: `{catalog}.{schema}` を開いて 4 テーブルを確認
# MAGIC - **Excel ファイル**: `/Volumes/{catalog}/{schema}/workshop_files/segment_targets.xlsx` をダウンロード
# MAGIC - **Lakeflow Designer**: 同じスキーマを Source として、ワークショップを開始

# COMMAND ----------

print("=" * 60)
print("Workshop data generation completed.")
print("=" * 60)
print(f"Catalog/Schema : {catalog}.{schema}")
print(f"Volume         : /Volumes/{catalog}/{schema}/workshop_files")
print(f"Excel file     : /Volumes/{catalog}/{schema}/workshop_files/segment_targets.xlsx")
print("=" * 60)
