# Databricks notebook source
# DBTITLE 1,パラメーターの設定
# Widgetsの作成
dbutils.widgets.text("catalog", "aibi_demo_catalog", "カタログ")
dbutils.widgets.text("schema", "bricksmart", "スキーマ")
dbutils.widgets.dropdown("recreate_schema", "False", ["True", "False"], "スキーマを再作成")

# Widgetからの値の取得
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
recreate_schema = dbutils.widgets.get("recreate_schema") == "True"

# COMMAND ----------

# DBTITLE 1,パラメーターのチェック
print(f"catalog: {catalog}")
print(f"schema: {schema}")
print(f"recreate_schema: {recreate_schema}")

if not catalog:
    raise ValueError("存在するカタログ名を入力してください")
if not schema:
    raise ValueError("スキーマ名を入力してください")

# COMMAND ----------

# DBTITLE 1,カタログ指定・スキーマの設定
# カタログを指定
spark.sql(f"USE CATALOG {catalog}")

# スキーマを再作成するかどうか
if recreate_schema:
    print(f"スキーマ {schema} を一度削除してから作成します")
    spark.sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE;")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
else:
    print(f"スキーマ {schema} が存在しない場合は作成します (存在する場合は何もしません)")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

# スキーマを使用
spark.sql(f"USE SCHEMA {schema}")

# COMMAND ----------

# DBTITLE 1,ユーザーデータ・商品データの生成
from pyspark.sql.functions import udf, expr, when, col, lit, round, rand, greatest, least, date_format, dayofweek, concat
from pyspark.sql.types import StringType

import datetime
import random
import string

def generate_username():
    # 5文字のランダムな小文字アルファベットを生成
    part1 = ''.join(random.choices(string.ascii_lowercase, k=5))
    part2 = ''.join(random.choices(string.ascii_lowercase, k=5))
    
    # 形式 xxxxx.xxxxx で結合
    username = f"{part1}.{part2}"
    return username

def generate_productname():
    # 5文字のランダムな小文字アルファベットを生成
    part1 = ''.join(random.choices(string.ascii_lowercase, k=3))
    part2 = ''.join(random.choices(string.ascii_lowercase, k=3))
    part3 = ''.join(random.choices(string.ascii_lowercase, k=3))
    
    # 形式 xxx_xxx_xxx で結合
    productname = f"{part1}_{part2}_{part3}"
    return productname

generate_username_udf = udf(generate_username, StringType())
generate_productname_udf = udf(generate_productname, StringType())

# ユーザーデータの生成
def generate_users(num_users=10000):
    """
    ユーザーデータを生成し、指定された数のデータを返します。
    
    パラメータ:
    num_users (int): 生成するユーザーの数 (デフォルトは10000)
    
    戻り値:
    DataFrame: 生成されたユーザー情報を含むSpark DataFrame
    
    各ユーザーには以下のカラムが含まれます:
    - user_id: ユーザーID (1からnum_usersまでの範囲)
    - name: ランダムなユーザー名
    - age: ランダムな年齢 (一様分布: 18歳以上78歳未満)
    - gender: 男性48%、女性47%、その他2%、未回答3%
    - email: ユーザー名を基にしたメールアドレス
    - registration_date: 固定の日付 (2020年1月1日)
    - region: 東京40%、大阪25%、北海道20%、福岡10%、沖縄5%
    """
    return (
        spark.range(1, num_users + 1)
        .withColumnRenamed("id", "user_id")
        .withColumn("name", generate_username_udf())
        .withColumn("age", round(rand() * 60 + 18))
        .withColumn("rand_gender", rand())
        .withColumn(
            "gender",
            when(col("rand_gender") < 0.02, lit("その他")) # 2%
            .when(col("rand_gender") < 0.05, lit("未回答")) # 0.02 + 0.03 (3%)
            .when(col("rand_gender") < 0.53, lit("男性")) # 0.05 + 0.48 (48%)
            .otherwise(lit("女性")) # 残り47%
        )
        .withColumn("email", concat(col("name"), lit("@example.com")))
        .withColumn("registration_date", lit(datetime.date(2020, 1, 1)))
        .withColumn("rand_region", rand())
        .withColumn(
            "region",
            when(col("rand_region") < 0.40, lit("東京")) # 40%
            .when(col("rand_region") < 0.65, lit("大阪")) # 40% + 25% = 65%
            .when(col("rand_region") < 0.85, lit("北海道")) # 65% + 20% = 85%
            .when(col("rand_region") < 0.95, lit("福岡")) # 85% + 10% = 95%
            .otherwise(lit("沖縄")) # 残り5%
        )
        .drop("rand_gender", "rand_region")
    )

# 商品データの生成
def generate_products(num_products=100):
    """
    商品データを生成し、指定された数のデータを返します。
    
    パラメータ:
    num_products (int): 生成する商品の数 (デフォルトは100)
    
    戻り値:
    DataFrame: 生成された商品情報を含むSpark DataFrame
    
    各商品には以下のカラムが含まれます:
    - product_id: 商品ID (1からnum_productsまでの範囲)
    - product_name: ランダムな商品名
    - category: カテゴリ (食料品50%、日用品50%)
    - subcategory: サブカテゴリ
      食料品の場合: 野菜25%、果物25%、健康食品25%、肉類25%
      日用品の場合: キッチン用品25%、スポーツ・アウトドア用品25%、医薬品25%、冷暖房器具25%
    - price: 商品価格 (100円以上1100円未満の範囲)
    - stock_quantity: 在庫数 (1以上101未満の範囲)
    - cost_price: 仕入れ価格 (販売価格の70%)
    """
    return (
        spark.range(1, num_products + 1)
        .withColumnRenamed("id", "product_id")
        .withColumn("product_name", generate_productname_udf())
        .withColumn("rand_category", rand())
        .withColumn(
            "category",
            when(col("rand_category") < 0.5, lit("食料品")).otherwise(lit("日用品"))
        )
        .withColumn("rand_subcategory", rand())
        .withColumn(
            "subcategory",
            when(
                col("category") == "食料品",
                when(col("rand_subcategory") < 0.25, lit("野菜"))
                .when(col("rand_subcategory") < 0.50, lit("果物"))
                .when(col("rand_subcategory") < 0.75, lit("健康食品"))
                .otherwise(lit("肉類"))
            ).otherwise(
                when(col("rand_subcategory") < 0.25, lit("キッチン用品"))
                .when(col("rand_subcategory") < 0.50, lit("スポーツ・アウトドア用品"))
                .when(col("rand_subcategory") < 0.75, lit("医薬品"))
                .otherwise(lit("冷暖房器具"))
            )
        )
        .withColumn("price", round(rand() * 1000 + 100, 2))
        .withColumn("stock_quantity", round(rand() * 100 + 1))
        .withColumn("cost_price", round(col("price") * 0.7, 2))
        .drop("rand_category", "rand_subcategory")
    )

users = generate_users()
products = generate_products()

display(users.limit(5))
display(products.limit(5))

# COMMAND ----------

# DBTITLE 1,テーブルの書き込み
users.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("users")
products.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("products")

# COMMAND ----------

# DBTITLE 1,販売取引データ・フィードバックデータの生成
# 購買行動に関する傾向スコア（重み）の設定
conditions = [
    # ---------- 地域ごとの傾向 ----------
    # 東京: 食生活において多様性を求める傾向があり、食料品の購入量が増える
    ((col("region") == "東京") & (col("category") == "食料品"), 1),

    # 大阪: 実用的な日用品の購入を好む
    ((col("region") == "大阪") & (col("category") == "日用品"), 1),

    # 福岡: 健康志向の高い野菜を多く購入
    ((col("region") == "福岡") & (col("subcategory") == "野菜"), 1),

    # 北海道: 寒冷地のため冷暖房器具の購入量が増える
    ((col("region") == "北海道") & (col("subcategory") == "冷暖房器具"), 2),

    # 沖縄: 地元の果物への関心が高い。さらに温暖な気候のため冷暖房器具の購入量が増える
    ((col("region") == "沖縄") & (col("subcategory") == "果物"), 1),
    ((col("region") == "沖縄") & (col("subcategory") == "冷暖房器具"), 1),

    # ---------- 性別ごとの傾向 ----------
    # 女性: 食料品や日用品、特にキッチン用品を多く購入
    ((col("gender") == "女性") & (col("category") == "食料品"), 1),
    ((col("gender") == "女性") & (col("category") == "日用品"), 1),
    ((col("gender") == "女性") & (col("subcategory") == "キッチン用品"), 1),

    # 男性: スポーツやアウトドア関連の商品に関心が高い。さらに肉類を好む傾向が強い
    ((col("gender") == "男性") & (col("category") == "スポーツ・アウトドア用品"), 2),
    ((col("gender") == "男性") & (col("subcategory") == "肉類"), 1),

    # ---------- 年齢層ごとの傾向 ----------
    # 若年層 (18〜34歳): 果物、肉類、スポーツ・アウトドア用品に関心が高い
    ((col("age") < 35) & (col("subcategory") == "果物"), 1),
    ((col("age") < 35) & (col("subcategory") == "肉類"), 2),
    ((col("age") < 35) & (col("subcategory") == "スポーツ・アウトドア用品"), 2),

    # 中年層 (35〜54歳): 健康志向が高まり野菜の購入量が増える。肉類もそれなりに購入。医薬品の購入量も増える
    ((col("age") >= 35) & (col("age") < 55) & (col("subcategory") == "野菜"), 1),
    ((col("age") >= 35) & (col("age") < 55) & (col("subcategory") == "肉類"), 1),
    ((col("age") >= 35) & (col("age") < 55) & (col("subcategory") == "医薬品"), 1),

    # シニア層 (55歳以上): 果物と野菜、医薬品の購入量が増える
    ((col("age") >= 55) & (col("subcategory") == "果物"), 2),
    ((col("age") >= 55) & (col("subcategory") == "野菜"), 2),
    ((col("age") >= 55) & (col("subcategory") == "医薬品"), 2),

    # ---------- 組み合わせによる傾向 ----------
    # 東京の若年層: 消費行動が旺盛で全体的な購入量が多い
    ((col("region") == "東京") & (col("age") < 35), 1),

    # 大阪の中年層: 家庭を持ち、食料品の購入量が増える
    ((col("region") == "大阪") & (col("age") >= 35) & (col("age") < 55) & (col("category") == "食料品"), 2),

    # 北海道の若年層: アウトドア活動に関連する日用品を購入する
    ((col("region") == "北海道") & (col("age") < 35) & (col("category") == "日用品"), 1),

    # 沖縄のシニア層は地元の伝統食に高い関心を持つ
    ((col("region") == "沖縄") & (col("age") >= 55) & (col("category") == "食料品"), 2),
]

# トランザクションデータの生成
def generate_transactions(users, products, num_transactions=1000000):
    """
    トランザクションデータを生成し、指定された数のデータを返します。

    パラメータ:
    users (DataFrame): ユーザーデータを含むSpark DataFrame
    products (DataFrame): 商品データを含むSpark DataFrame
    num_transactions (int): 生成するトランザクションの数 (デフォルトは1000000)

    戻り値:
    DataFrame: 生成されたトランザクション情報を含むSpark DataFrame

    各トランザクションには以下のカラムが含まれます:
    - transaction_id: トランザクションID (1からnum_transactionsまでの範囲)
    - user_id: ユーザーID (1から登録ユーザー数までの範囲)
    - product_id: 商品ID (1から登録商品数までの範囲)
    - quantity: 購入数量 (1以上6以下の整数、傾向スコアによって調整)
    - store_id: 店舗ID (1以上11以下の整数)
    - transaction_date: 取引日 (2023年1月1日から2024年1月1日までの範囲)
        - 8月と12月は10%の確率で特定の日付を選択
        - 週末は10%の確率で特定の日付を選択
    - transaction_price: 取引金額 (quantity * price)

    傾向スコア:
    ユーザーの属性や商品カテゴリに基づいて購入数量を調整します。
    最終的な数量は0以上の範囲に収まるように調整されます。
    """
    transactions = (
        spark.range(1, num_transactions + 1).withColumnRenamed("id", "transaction_id")
        .withColumn("user_id", expr(f"floor(rand() * {users.count()}) + 1"))
        .withColumn("product_id", expr(f"floor(rand() * {products.count()}) + 1"))
        .withColumn("quantity", round(rand() * 5 + 1))
        .withColumn("store_id", round(rand() * 10 + 1))
        .withColumn("random_date", expr("date_add(date('2024-01-01'), -CAST(rand() * 365 AS INTEGER))"))
        .withColumn("month", date_format("random_date", "M").cast("int"))
        .withColumn("is_weekend", dayofweek("random_date").isin([1, 7]))
        .withColumn("transaction_date", 
            when((rand() < 0.1) & ((expr("month") == 8) | (expr("month") == 12)), expr("random_date"))
            .when((rand() < 0.1) & expr("is_weekend"), expr("random_date"))
            .otherwise(expr("date_add(date('2024-01-01'), -CAST(rand() * 365 AS INTEGER))"))
        )
        .drop("random_date", "month", "is_weekend")
    )

    # 傾向スコアに基づいて購入数量を調整
    adjusted_transaction = transactions.join(users, "user_id").join(products.select("product_id", "price", "category", "subcategory"), "product_id")
    for condition, adjustment in conditions:
        adjusted_transaction = adjusted_transaction.withColumn("quantity", when(condition, col("quantity") + adjustment).otherwise(col("quantity")))
    adjusted_transaction = adjusted_transaction.withColumn("quantity", greatest(lit(0), "quantity"))
    adjusted_transaction = adjusted_transaction.withColumn("transaction_price", col("quantity") * col("price"))

    # 調整済みトランザクションデータを返却
    return adjusted_transaction.select("transaction_id", "user_id", "product_id", "quantity", "transaction_price", "transaction_date", "store_id")

# フィードバックデータの生成
def generate_feedbacks(users, products, num_feedbacks=50000):
    """
    フィードバックデータを生成し、指定された数のデータを返します。
    
    パラメータ:
    users (DataFrame): ユーザーデータを含むSpark DataFrame
    products (DataFrame): 商品データを含むSpark DataFrame
    num_feedbacks (int): 生成するフィードバックの数 (デフォルトは50000)
    
    戻り値:
    DataFrame: 生成されたフィードバック情報を含むSpark DataFrame
    
    各フィードバックには以下のカラムが含まれます:
    - feedback_id: フィードバックID (1からnum_feedbacksまでの範囲)
    - user_id: ユーザーID (1から登録ユーザー数までの範囲)
    - product_id: 商品ID (1から登録商品数までの範囲)
    - rating: 評価 (1以上5以下の整数、傾向スコアによって調整)
    - date: フィードバック日付 (2021年1月1日から2022年1月1日までの範囲)
    - type: フィードバック種別 (商品45%、サービス45%、その他10%)
    - comment: コメント (Feedback_[feedback_id]の形式)
    
    傾向スコア:
    ユーザーの属性や商品カテゴリに基づいて評価を調整します。
    最終的な評価は0以上5以下の範囲に収まるように調整されます。
    """
    feedbacks = (
        spark.range(1, num_feedbacks + 1)
        .withColumnRenamed("id", "feedback_id")
        .withColumn("user_id", expr(f"floor(rand() * {users.count()}) + 1"))
        .withColumn("product_id", expr(f"floor(rand() * {products.count()}) + 1"))
        .withColumn("rating", round(rand() * 4 + 1))
        .withColumn("date", expr("date_add(date('2022-01-01'), -CAST(rand() * 365 AS INTEGER))"))
        .withColumn("rand_type", rand())
        .withColumn(
            "type",
            when(col("rand_type") < 0.45, lit("商品"))
            .when(col("rand_type") < 0.90, lit("サービス"))
            .otherwise(lit("その他"))
        )
        .drop("rand_type")
        .withColumn("comment", expr("concat('Feedback_', feedback_id)"))
    )
    
    # 傾向スコアに基づいて評価を調整
    adjusted_feedbacks = feedbacks.join(users, "user_id").join(products.select("product_id", "category", "subcategory"), "product_id")
    for condition, adjustment in conditions:
        adjusted_feedbacks = adjusted_feedbacks.withColumn("rating",
            when(condition, col("rating") + adjustment).otherwise(col("rating")))
    adjusted_feedbacks = adjusted_feedbacks.withColumn("rating",greatest(lit(0), least(lit(5), "rating")))

    # 調整済みフィードバックデータを返却
    return adjusted_feedbacks.select("feedback_id", "user_id", "product_id", "rating", "date", "type", "comment")

users = spark.table("users")
products = spark.table("products")
transactions = generate_transactions(users, products)
feedbacks = generate_feedbacks(users, products)

# 結果の表示（データフレームのサイズによっては表示が重くなる可能性があるため、小さなサンプルで表示）
display(transactions.limit(5))
display(feedbacks.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC Note: トランザクションとフィードバックのテーブルへの書き込みについて、リネージの流れを直感的に分かりやすいものにするために一旦一時テーブルに書き込み、DEEP CLONEを使用してメインテーブルを作成する。

# COMMAND ----------

# DBTITLE 1,一時テーブルへの書き込み
transactions.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("transactions_temp")
feedbacks.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("feedbacks_temp")

# COMMAND ----------

# DBTITLE 1,DEEP CLONEを使用して一時テーブルからメインテーブルを作成
spark.sql("DROP TABLE IF EXISTS transactions")
spark.sql("CREATE TABLE transactions DEEP CLONE transactions_temp")
spark.sql("DROP TABLE IF EXISTS feedbacks")
spark.sql("CREATE TABLE feedbacks DEEP CLONE feedbacks_temp")

# COMMAND ----------

# DBTITLE 1,一時テーブルの削除
spark.sql("DROP TABLE transactions_temp")
spark.sql("DROP TABLE feedbacks_temp")

# COMMAND ----------

# DBTITLE 1,テーブルのメタデータ編集
# MAGIC %sql
# MAGIC ALTER TABLE users ALTER COLUMN user_id COMMENT "ユーザーID";
# MAGIC ALTER TABLE users ALTER COLUMN name COMMENT "氏名";
# MAGIC ALTER TABLE users ALTER COLUMN age COMMENT "年齢: 0以上";
# MAGIC ALTER TABLE users ALTER COLUMN gender COMMENT "性別: 例) 男性, 女性, 未回答, その他";
# MAGIC ALTER TABLE users ALTER COLUMN email COMMENT "メールアドレス";
# MAGIC ALTER TABLE users ALTER COLUMN registration_date COMMENT "登録日";
# MAGIC ALTER TABLE users ALTER COLUMN region COMMENT "地域: 例) 東京, 大阪, 北海道";
# MAGIC COMMENT ON TABLE users IS '**users テーブル**\nオンラインスーパー「ブリックスマート」に登録されているユーザー情報を保持するテーブルです。\n- ユーザーの基本情報（氏名、年齢、性別、地域など）や連絡先（メールアドレス）を管理\n- ユーザーのセグメンテーションや嗜好分析、マーケティング効果測定などに活用できます';
# MAGIC
# MAGIC ALTER TABLE transactions ALTER COLUMN transaction_id COMMENT "トランザクションID";
# MAGIC ALTER TABLE transactions ALTER COLUMN user_id COMMENT "ユーザーID: usersテーブルのuser_idとリンクする外部キー";
# MAGIC ALTER TABLE transactions ALTER COLUMN transaction_date COMMENT "購入日";
# MAGIC ALTER TABLE transactions ALTER COLUMN product_id COMMENT "商品ID: productsテーブルのproduct_idとリンクする外部キー";
# MAGIC ALTER TABLE transactions ALTER COLUMN quantity COMMENT "購入数量: 1以上";
# MAGIC ALTER TABLE transactions ALTER COLUMN transaction_price COMMENT "購入時価格: 0以上, transactions.quantity * products.price で計算";
# MAGIC ALTER TABLE transactions ALTER COLUMN store_id COMMENT "店舗ID";
# MAGIC COMMENT ON TABLE transactions IS '**transactions テーブル**\nオンラインスーパー「ブリックスマート」で行われた販売取引（購入履歴）の情報を管理するテーブルです。\n- ユーザーIDや商品IDなど他テーブルと関連付けしつつ、購入日や価格、数量などを保持\n- 販売動向の分析、ユーザーの購買行動追跡、在庫・マーケティング戦略の最適化に役立ちます';
# MAGIC
# MAGIC ALTER TABLE products ALTER COLUMN product_id COMMENT "商品ID";
# MAGIC ALTER TABLE products ALTER COLUMN product_name COMMENT "商品名";
# MAGIC ALTER TABLE products ALTER COLUMN category COMMENT "カテゴリー: 例) 食料品, 日用品";
# MAGIC ALTER TABLE products ALTER COLUMN subcategory COMMENT "サブカテゴリー: 例) 野菜, 洗剤";
# MAGIC ALTER TABLE products ALTER COLUMN price COMMENT "販売価格: 0以上";
# MAGIC ALTER TABLE products ALTER COLUMN stock_quantity COMMENT "在庫数量";
# MAGIC ALTER TABLE products ALTER COLUMN cost_price COMMENT "仕入れ価格";
# MAGIC COMMENT ON TABLE products IS '**products テーブル**\nオンラインスーパー「ブリックスマート」で取り扱う商品の情報を管理するテーブルです。\n- 商品名、カテゴリー・サブカテゴリー、価格、在庫数、原価などを保持\n- 在庫管理、価格分析、商品分類や商品のパフォーマンス分析に活用できます';
# MAGIC
# MAGIC ALTER TABLE feedbacks ALTER COLUMN feedback_id COMMENT "フィードバックID";
# MAGIC ALTER TABLE feedbacks ALTER COLUMN user_id COMMENT "ユーザーID: usersテーブルのuser_idとリンクする外部キー";
# MAGIC ALTER TABLE feedbacks ALTER COLUMN comment COMMENT "コメント";
# MAGIC ALTER TABLE feedbacks ALTER COLUMN date COMMENT "フィードバック日";
# MAGIC ALTER TABLE feedbacks ALTER COLUMN type COMMENT "フィードバック種別: 商品, サービス, その他";
# MAGIC ALTER TABLE feedbacks ALTER COLUMN rating COMMENT "評価: 1～5";
# MAGIC COMMENT ON TABLE feedbacks IS '**feedbacks テーブル**\nユーザーからのフィードバックを管理するテーブルです。\n- 商品やサービスに対するコメント、評価(1～5)、フィードバック日などを保持\n- ユーザー満足度の把握や改善点の分析、優先度付けに役立ちます';

# COMMAND ----------

# DBTITLE 1,gold_usersテーブルの生成
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_user AS (
# MAGIC   -- ユーザーごとの購買・評価データを集計
# MAGIC   with user_metrics as (
# MAGIC   SELECT 
# MAGIC     u.user_id,
# MAGIC     CASE 
# MAGIC       WHEN u.age < 35 THEN '若年層'
# MAGIC       WHEN u.age < 55 THEN '中年層'
# MAGIC       ELSE 'シニア層'
# MAGIC     END as age_group,
# MAGIC     SUM(CASE WHEN p.category = '食料品' THEN t.quantity ELSE 0 END) AS food_quantity,
# MAGIC     SUM(CASE WHEN p.category = '日用品' THEN t.quantity ELSE 0 END) AS daily_quantity,
# MAGIC     SUM(CASE WHEN p.category NOT IN ('食料品', '日用品') THEN t.quantity ELSE 0 END) AS other_quantity,
# MAGIC     AVG(CASE WHEN p.category = '食料品' THEN f.rating ELSE NULL END) AS food_rating,
# MAGIC     AVG(CASE WHEN p.category = '日用品' THEN f.rating ELSE NULL END) AS daily_rating,
# MAGIC     AVG(CASE WHEN p.category NOT IN ('食料品', '日用品') THEN f.rating ELSE NULL END) AS other_rating
# MAGIC   FROM users u
# MAGIC   LEFT JOIN transactions t ON u.user_id = t.user_id
# MAGIC   LEFT JOIN products p ON t.product_id = p.product_id
# MAGIC   LEFT JOIN feedbacks f ON u.user_id = f.user_id
# MAGIC   GROUP BY u.user_id, u.age)
# MAGIC   -- ユーザー基本情報と購買・評価指標を結合
# MAGIC   SELECT * FROM users JOIN user_metrics USING (user_id)
# MAGIC );

# COMMAND ----------

# DBTITLE 1,gold_usersテーブルのメタデータ編集
# MAGIC %sql
# MAGIC ALTER TABLE gold_user ALTER COLUMN age_group COMMENT "年齢層: 若年層, 中年層, シニア層\n\n- 若年層: 35歳未満\n- 中年層: 35歳以上55歳未満\n- シニア層: 55歳以上";
# MAGIC ALTER TABLE gold_user ALTER COLUMN food_quantity COMMENT "食料品の合計購買点数";
# MAGIC ALTER TABLE gold_user ALTER COLUMN daily_quantity COMMENT "日用品の合計購買点数";
# MAGIC ALTER TABLE gold_user ALTER COLUMN other_quantity COMMENT "その他の合計購買点数";
# MAGIC ALTER TABLE gold_user ALTER COLUMN food_rating COMMENT "食料品の平均レビュー評価";
# MAGIC ALTER TABLE gold_user ALTER COLUMN daily_rating COMMENT "日用品の平均レビュー評価";
# MAGIC ALTER TABLE gold_user ALTER COLUMN other_rating COMMENT "その他の平均レビュー評価";
# MAGIC COMMENT ON TABLE gold_user IS '**gold_user テーブル**\nAIを搭載した食品推薦システムに登録したユーザーに関する情報が含まれています。\n- 人口統計学的詳細、食品消費習慣、および評価などを保持\n- ユーザーの嗜好を理解し、食品の消費傾向を追跡、AIシステムの有効性を評価するのに活用\n- 個々のユーザーに合わせた食品推薦やシステム改善の検討にも役立ちます';

# COMMAND ----------

# DBTITLE 1,PIIタグの追加
# MAGIC %sql
# MAGIC ALTER TABLE users ALTER COLUMN name SET TAGS ('pii_name');
# MAGIC ALTER TABLE users ALTER COLUMN email SET TAGS ('pii_email');
# MAGIC ALTER TABLE gold_user ALTER COLUMN name SET TAGS ('pii_name');
# MAGIC ALTER TABLE gold_user ALTER COLUMN email SET TAGS ('pii_email');

# COMMAND ----------

# DBTITLE 1,PK & FKの追加
# MAGIC %sql
# MAGIC ALTER TABLE users ALTER COLUMN user_id SET NOT NULL;
# MAGIC ALTER TABLE transactions ALTER COLUMN transaction_id SET NOT NULL;
# MAGIC ALTER TABLE products ALTER COLUMN product_id SET NOT NULL;
# MAGIC ALTER TABLE feedbacks ALTER COLUMN feedback_id SET NOT NULL;
# MAGIC ALTER TABLE gold_user ALTER COLUMN user_id SET NOT NULL;

# MAGIC ALTER TABLE users ADD CONSTRAINT users_pk PRIMARY KEY (user_id);
# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_pk PRIMARY KEY (transaction_id);
# MAGIC ALTER TABLE products ADD CONSTRAINT products_pk PRIMARY KEY (product_id);
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_pk PRIMARY KEY (feedback_id);
# MAGIC ALTER TABLE gold_user ADD CONSTRAINT gold_user_pk PRIMARY KEY (user_id);

# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_users_fk FOREIGN KEY (user_id) REFERENCES users (user_id) NOT ENFORCED;
# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_products_fk FOREIGN KEY (product_id) REFERENCES products (product_id) NOT ENFORCED;
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_users_fk FOREIGN KEY (user_id) REFERENCES users (user_id) NOT ENFORCED;
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_products_fk FOREIGN KEY (product_id) REFERENCES products (product_id) NOT ENFORCED;

# COMMAND ----------

# DBTITLE 1,列レベルマスキングの追加
try:
    # マスキング関数の作成
    spark.sql("""
    CREATE FUNCTION IF NOT EXISTS mask_email(email STRING) 
    RETURN CASE WHEN is_member('admins') THEN email ELSE '***@example.com' END
    """)
    
    # usersテーブルにマスキングを適用
    spark.sql("""
    ALTER TABLE users ALTER COLUMN email SET MASK mask_email
    """)
    
    # gold_userテーブルにマスキングを適用
    spark.sql("""
    ALTER TABLE gold_user ALTER COLUMN email SET MASK mask_email
    """)
    
    print("列レベルマスキングの適用が完了しました。")
    
except Exception as e:
    print(f"列レベルマスキングの適用中にエラーが発生しました: {str(e)}")
    print("このエラーはDBR 15.4より前のバージョンで実行している場合に発生する可能性があります。")

# COMMAND ----------

# DBTITLE 1,認定済みタグの追加
certified_tag = 'system.Certified'

try:
    spark.sql(f"ALTER TABLE users SET TAGS ('{certified_tag}')")
    spark.sql(f"ALTER TABLE transactions SET TAGS ('{certified_tag}')")
    spark.sql(f"ALTER TABLE products SET TAGS ('{certified_tag}')")
    spark.sql(f"ALTER TABLE feedbacks SET TAGS ('{certified_tag}')")
    spark.sql(f"ALTER TABLE gold_user SET TAGS ('{certified_tag}')")
    print(f"認定済みタグ '{certified_tag}' の追加が完了しました。")

except Exception as e:
    print(f"認定済みタグ '{certified_tag}' の追加中にエラーが発生しました: {str(e)}")
    print("このエラーはタグ機能に対応していないワークスペースで実行した場合に発生する可能性があります。")

# COMMAND ----------

# DBTITLE 1,地域ごとの商品カテゴリの売上高と売上比率を計算
# MAGIC %sql
# MAGIC WITH region_sales AS (
# MAGIC   SELECT
# MAGIC     u.region,
# MAGIC     p.category,
# MAGIC     SUM(t.transaction_price) AS total_sales
# MAGIC   FROM
# MAGIC     transactions t
# MAGIC   JOIN
# MAGIC     users u ON t.user_id = u.user_id
# MAGIC   JOIN
# MAGIC     products p ON t.product_id = p.product_id
# MAGIC   WHERE
# MAGIC     t.transaction_price IS NOT NULL
# MAGIC     AND u.region IS NOT NULL
# MAGIC   GROUP BY
# MAGIC     u.region,
# MAGIC     p.category
# MAGIC ),
# MAGIC total_region_sales AS (
# MAGIC   SELECT
# MAGIC     region,
# MAGIC     SUM(total_sales) AS region_total_sales
# MAGIC   FROM
# MAGIC     region_sales
# MAGIC   GROUP BY
# MAGIC     region
# MAGIC )
# MAGIC SELECT
# MAGIC   region_sales.region,
# MAGIC   region_sales.category,
# MAGIC   FLOOR(region_sales.total_sales),
# MAGIC   ROUND((region_sales.total_sales / total_region_sales.region_total_sales) * 100, 2) AS sales_ratio
# MAGIC FROM
# MAGIC   region_sales JOIN total_region_sales ON region_sales.region = total_region_sales.region
# MAGIC ORDER BY
# MAGIC   region_sales.region,
# MAGIC   region_sales.category;

# COMMAND ----------

# DBTITLE 1,性別ごとの商品カテゴリの売上高と売上比率を計算
# MAGIC %sql
# MAGIC WITH gender_sales AS (
# MAGIC   SELECT
# MAGIC     u.gender,
# MAGIC     p.category,
# MAGIC     SUM(t.transaction_price) AS total_sales
# MAGIC   FROM
# MAGIC     transactions t
# MAGIC   JOIN
# MAGIC     users u ON t.user_id = u.user_id
# MAGIC   JOIN
# MAGIC     products p ON t.product_id = p.product_id
# MAGIC   WHERE
# MAGIC     t.transaction_price IS NOT NULL
# MAGIC     AND u.gender IS NOT NULL
# MAGIC   GROUP BY
# MAGIC     u.gender,
# MAGIC     p.category
# MAGIC ),
# MAGIC total_gender_sales AS (
# MAGIC   SELECT
# MAGIC     gender,
# MAGIC     SUM(total_sales) AS gender_total_sales
# MAGIC   FROM
# MAGIC     gender_sales
# MAGIC   GROUP BY
# MAGIC     gender
# MAGIC )
# MAGIC SELECT
# MAGIC   gender_sales.gender,
# MAGIC   gender_sales.category,
# MAGIC   FLOOR(gender_sales.total_sales),
# MAGIC   ROUND((gender_sales.total_sales / total_gender_sales.gender_total_sales) * 100, 2) AS sales_ratio
# MAGIC FROM
# MAGIC   gender_sales
# MAGIC JOIN
# MAGIC   total_gender_sales ON gender_sales.gender = total_gender_sales.gender
# MAGIC ORDER BY
# MAGIC   gender_sales.gender,
# MAGIC   gender_sales.category;

# COMMAND ----------

# DBTITLE 1,年齢層ごとの商品カテゴリの売上高と売上比率を計算
# MAGIC %sql
# MAGIC WITH age_group_sales AS (
# MAGIC   SELECT
# MAGIC     gu.age_group,
# MAGIC     p.category,
# MAGIC     SUM(t.transaction_price) AS total_sales
# MAGIC   FROM
# MAGIC     transactions t
# MAGIC   JOIN
# MAGIC     gold_user gu ON t.user_id = gu.user_id
# MAGIC   JOIN
# MAGIC     products p ON t.product_id = p.product_id
# MAGIC   WHERE
# MAGIC     t.transaction_price IS NOT NULL
# MAGIC     AND gu.age_group IS NOT NULL
# MAGIC   GROUP BY
# MAGIC     gu.age_group,
# MAGIC     p.category
# MAGIC ),
# MAGIC total_age_group_sales AS (
# MAGIC   SELECT
# MAGIC     age_group,
# MAGIC     SUM(total_sales) AS age_group_total_sales
# MAGIC   FROM
# MAGIC     age_group_sales
# MAGIC   GROUP BY
# MAGIC     age_group
# MAGIC )
# MAGIC SELECT
# MAGIC   age_group_sales.age_group,
# MAGIC   age_group_sales.category,
# MAGIC   FLOOR(age_group_sales.total_sales),
# MAGIC   ROUND((age_group_sales.total_sales / total_age_group_sales.age_group_total_sales) * 100, 2) AS sales_ratio
# MAGIC FROM
# MAGIC   age_group_sales
# MAGIC JOIN
# MAGIC   total_age_group_sales ON age_group_sales.age_group = total_age_group_sales.age_group
# MAGIC ORDER BY
# MAGIC   age_group_sales.age_group,
# MAGIC   age_group_sales.category;
