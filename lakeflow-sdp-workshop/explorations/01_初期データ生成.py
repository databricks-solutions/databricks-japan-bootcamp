# Databricks notebook source
# MAGIC %run ./00_環境設定

# COMMAND ----------

# MAGIC %md
# MAGIC # 顧客データ生成 (CDF)

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
        .withColumn("random_date", expr("date_add(date('2023-01-01'), -CAST(rand() * 30 AS INTEGER))"))
        .withColumn("month", date_format("random_date", "M").cast("int"))
        .withColumn("is_weekend", dayofweek("random_date").isin([1, 7]))
        .withColumn("last_updated",
            when((rand() < 0.1) & ((expr("month") == 8) | (expr("month") == 12)), expr("random_date"))
            .when((rand() < 0.1) & expr("is_weekend"), expr("random_date"))
            .otherwise(expr("date_add(date('2023-01-01'), -CAST(rand() * 30 AS INTEGER))"))
        )
        .withColumn("operation", lit("INSERT"))
        .drop("random_date", "month", "is_weekend")
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

transactions = generate_transactions(users, products)
feedbacks = generate_feedbacks(users, products)

# 結果の表示（データフレームのサイズによっては表示が重くなる可能性があるため、小さなサンプルで表示）
display(transactions.limit(5))
display(feedbacks.limit(5))

# COMMAND ----------

# DBTITLE 1,購買履歴を東日本エリアと西日本エリアに分割
# 西日本・東日本の地域リスト
west_regions = ["大阪", "福岡", "沖縄"]
east_regions = ["東京", "北海道"]

# transactionsにusersを結合
tx_with_region = transactions.join(users.select("user_id", "region"), on="user_id", how="inner")

# 西日本のレコード
transactions_west = tx_with_region.filter(col("region").isin(west_regions)).select("transaction_id", "user_id", "product_id", "quantity", "transaction_price", "transaction_date", "store_id")

# 東日本のレコード
transactions_east = tx_with_region.filter(col("region").isin(east_regions)).select("transaction_id", "user_id", "product_id", "quantity", "transaction_price", "transaction_date", "store_id")

display(transactions_west.limit(5))
display(transactions_east.limit(5))

# COMMAND ----------

# DBTITLE 1,初期データの書き込み
import random
import string

def generate_unique_code(length=5):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.sample(chars, length))

random_suffix = generate_unique_code()

# 顧客情報の書き出し (CSV)
users.toPandas().to_csv(f'{users_dir}users_{random_suffix}.csv', index=False, encoding='utf-8-sig')

# 購入履歴の書き出し (CSV)
transactions_west.toPandas().to_csv(f'{transactions_west_dir}transactions_west_{random_suffix}.csv', index=False, encoding='utf-8-sig')
transactions_east.toPandas().to_csv(f'{transactions_east_dir}transactions_east_{random_suffix}.csv', index=False, encoding='utf-8-sig')

# 商品データの書き出し (CSV)
products.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(products_source_table)
