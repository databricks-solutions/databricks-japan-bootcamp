# Databricks notebook source
# DBTITLE 1,パラメーターの設定
# Widgetsの作成
dbutils.widgets.text("catalog", "workspace", "カタログ")
dbutils.widgets.text("schema", "bricksmart", "スキーマ")
dbutils.widgets.dropdown("recreate_schema", "False", ["True", "False"], "スキーマを再作成")
dbutils.widgets.text("volume", "csv", "ボリューム")
dbutils.widgets.dropdown("recreate_volume", "False", ["True", "False"], "ボリュームを再作成")

# Widgetからの値の取得
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
recreate_schema = dbutils.widgets.get("recreate_schema") == "True"
volume = dbutils.widgets.get("volume")
recreate_volume = dbutils.widgets.get("recreate_volume") == "True"

# COMMAND ----------

# DBTITLE 1,パラメーターのチェック
print(f"catalog: {catalog}")
print(f"schema: {schema}")
print(f"recreate_schema: {recreate_schema}")
print(f"volume: {volume}")
print(f"recreate_volume: {recreate_volume}")

if not catalog:
    raise ValueError("存在するカタログ名を入力してください")
if not schema:
    raise ValueError("スキーマ名を入力してください")
if not volume:
    raise ValueError("ボリューム名を入力してください")

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

# ボリュームを再作成するかどうか
if recreate_volume:
    print(f"ボリューム {volume} を一度削除してから作成します")
    spark.sql(f"DROP VOLUME IF EXISTS {catalog}.{schema}.{volume};")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")

else:
    print(f"ボリューム {volume} が存在しない場合は作成します (存在する場合は何もしません)")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")


# COMMAND ----------

# DBTITLE 1,テーブルALL削除
# # スキーマ内のすべてのテーブル名を取得する
# tables_df = spark.sql(f"SHOW TABLES IN {catalog}.{schema}")

# # テーブル名が "gold_" で始まるテーブルのみ削除する
# for table in tables_df.collect():
#     table_name = table["tableName"]
#     spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.{table_name}")
#     print(f"削除されたテーブル: {table_name}")

# print(f"{catalog}.{schema}配下の全てのテーブルが削除されました。")


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

# DBTITLE 1,販売取引データの生成・フィードバックデータの準備
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
    - date: フィードバック日付 (2024年1月1日から2025年1月1日までの範囲)
    - comment: コメント (自由記述形式)
    
    傾向スコア:
    ユーザーの属性や商品カテゴリに基づいて評価を調整します。
    最終的な評価は0以上5以下の範囲に収まるように調整されます。
    """
    feedbacks_pre = (
        spark.range(1, num_feedbacks + 1)
        .withColumnRenamed("id", "feedback_id")
        .withColumn("user_id", expr(f"floor(rand() * {users.count()}) + 1"))
        .withColumn("product_id", expr(f"floor(rand() * {products.count()}) + 1"))
        .withColumn("rating", round(rand() * 4 + 1))
        .withColumn("date", expr("date_add(date('2024-01-01'), -CAST(rand() * 365 AS INTEGER))"))
    )
    
    # 傾向スコアに基づいて評価を調整
    adjusted_feedbacks = feedbacks_pre.join(users, "user_id").join(products.select("product_id", "category", "subcategory"), "product_id")
    for condition, adjustment in conditions:
        adjusted_feedbacks = adjusted_feedbacks.withColumn("rating",
            when(condition, col("rating") + adjustment).otherwise(col("rating")))
    adjusted_feedbacks = adjusted_feedbacks.withColumn("rating",greatest(lit(0), least(lit(5), "rating")))

    # 調整済みフィードバックデータを返却
    return adjusted_feedbacks.select("feedback_id", "user_id", "product_id", "rating", "date")

users = spark.table("users")
products = spark.table("products")
transactions = generate_transactions(users, products)
feedbacks_pre = generate_feedbacks(users, products, 200)    #デモ用に件数絞る

# 結果の表示（データフレームのサイズによっては表示が重くなる可能性があるため、小さなサンプルで表示）
display(transactions.limit(5))
display(feedbacks_pre.limit(5))

# COMMAND ----------

# DBTITLE 1,フィードバックデータのマスタ準備
# ===========================================================
# フィードバックのコメントとレーティングの定義
# ===========================================================
import pandas as pd
from pyspark.sql import functions as F, Window

# フィードバックデータ
reviews_with_rating = [
    # ── 品揃え ────────────────────────────────────────────
    ("ここに来ると、本当に欲しかった商品がいつも見つかる！他の店では見かけないような珍しい商品まで取り揃えていて、毎回驚かされます。", 5),
    ("ここのお店の食材は本当に新鮮で美味しい！特にお肉や魚は質が高くて、他のどの店でも同じクオリティは見たことがない。信頼しています。", 5),
    ("常に新しい商品が入っていて、毎回訪れるのが楽しみです！新商品を見つけると、必ず手に取ってしまいます。", 4),
    ("品揃えが豊富で、欲しい商品がだいたい揃っています。時々珍しい商品も見かけるので、そこも良いところです。", 4),
    ("品揃えは悪くないですが、時々欲しい商品が売り切れていることがあります。もう少し在庫を多くしてもらえると嬉しいです。", 2),
    ("品揃えがひどい。欲しい商品が全く置いていないし、他の店舗で見かける商品すらない。何度も行ってもがっかりするばかりです。", 1),
    ("おかずコーナーの品揃えは悪くないけれど、いつも同じなのでもっと工夫してもらえると嬉しいです。全体的には満足しています。", 3),

    # ── 品質（鮮度・商品クオリティ） ───────────────────────
    ("ここの商品は全体的に良い品質だと思います。特に野菜や果物は新鮮で、美味しいです。", 4),
    ("新商品がたまに入っているので、足を運ぶたびに少し新しい発見があるのが良い点です。", 4),
    ("おかずはまずまずですが、たまにおいしくないものもあります。それでも安いので利用しています。", 3),
    ("新商品は時々見かけますが、他の店に比べると少し遅いかなと感じることがあります。", 2),
    ("生鮮食品は悪くないですが、たまに少し新鮮さに欠けることがあります。それでも、他の店に比べればまだマシです。", 3),
    ("チラシの商品がすぐなくなる時があり、せっかく来店しても在庫切れで悲しく帰るしかないこともあります。全体的には満足しているので在庫だけもっとあると嬉しいです。", 4),
    ("商品の品質には少しばらつきがあります。特に果物や野菜は時々傷んでいることがあるので、もっと新鮮なものを期待していました。", 3),
    ("新商品があまり頻繁に入ってこないのが残念です。入れ替えのペースが遅いように感じます。", 2),

    # ── コスパ・お得感 ──────────────────────────────────
    ("この店の価格は本当に素晴らしい！他の店では考えられないほど安くて、高品質の商品が手に入ります。特にお得感があり、いつも満足しています。", 5),
    ("セールが大変充実していて、欲しかった商品が驚きの価格で手に入ることが多いです。毎回訪れるたびにお得な買い物ができて、本当にありがたいです。", 5),
    ("ポイント還元率が非常に高くて、割引制度も素晴らしい！何度も利用しているうちに、どんどんお得になっていく感覚があって、絶対にお得感があります。", 5),
    ("価格は適正だと思います。高すぎず、安すぎず、ちょうどいい価格帯で購入しやすいです。特に不満はないですが、もっとお得だと嬉しいです。", 4),
    ("価格は少し高めに感じますが、特に不満があるわけではないです。もう少し安くなれば嬉しいですが、仕方ないかなとも思っています。", 3),
    ("ここは本当に高すぎます。価格設定が非常に不満で、他の店と比べても倍以上の価格で買わされていると感じます。もう二度と買いません。", 1),
    ("セールや特売がたまに行われていて、割引もあるので嬉しいです。もっと頻繁にやってくれるとありがたいですね。", 5),
    ("ポイント還元や割引があるのは嬉しいですが、他の店に比べると少しだけ劣る感じがします。でも、悪くはないです。", 4),
    ("価格はまあまあで、安すぎることはないですが、高すぎることもない感じです。特別安いわけではないですが、普通に満足しています。", 4),
    ("セールや特売がたまに行われていて、まあまあお得に感じます。ただ、頻繁にあるわけではないので、もっとあればいいなと思います。", 4),
    ("ポイント還元や割引があって、そこそこお得感はありますが、他の店ほどのインパクトは感じません。悪くはないけれど、もっと充実しているとさらに良いです。", 4),
    ("セールや特売が時々ありますが、他の店舗と比べると少し物足りない感じがします。まあ、あっても利用するかどうかはその時次第ですが。", 3),
    ("ポイント還元や割引があるけど、他の店に比べてそこまでお得感はありません。もう少し優遇されているといいなと思います。", 3),
    ("価格が高いと感じることが多いです。特に他の店ではもっと安く買えることがあるので、ここでは少し割高に思ってしまいます。", 2),
    ("セールや特売があまり頻繁に行われないので、少しがっかりしています。お得感があまりないので、他の店に比べて魅力を感じにくいです。", 2),
    ("ポイント還元や割引があっても、正直他の店ほどのインパクトはありません。もっと魅力的な制度を提供してほしいと思っています。", 3),
    ("セールや特売がほとんどなく、あっても期待外れです。価格が高いままで、割引の幅も少なく、完全にがっかりしています。", 2),
    ("ポイント還元も割引制度も最悪です。全くお得感がなく、他の店舗に比べて圧倒的に損した気分になります。もう利用することはないでしょう。", 1),

    # ── 接客・サービス ──────────────────────────────────
    ("価格に対して商品やサービスのクオリティが非常に高いです。どこに行ってもここが一番お得だと思います。", 5),
    ("スタッフの対応はとても良かったです。商品について詳しく説明してくれたり、質問にも親切に答えてくれたので安心して買い物ができました。ただ、もう少しスピードが速ければ、さらに良かったと思います。", 5),
    ("レジでの対応はスムーズで、スタッフの笑顔がとても印象的でした。商品の袋詰めも丁寧にしてくれました。ただ、少し混雑していたため、もう少し早く対応してくれるともっと嬉しかったです。", 4),
    ("価格と商品の質は満足しています。安い価格帯の商品でもしっかりとした品質を保っており、良い買い物ができました。ただ、少し高めの商品を買う際には、もう少しサービス面でも特別感があると、さらに満足感が高くなったかなと思います。", 3),
    ("スタッフの対応は悪くはないですが、他の店と比べると少しそっけない印象を受けました。説明が少し不十分に感じることもありましたが、特に大きな問題ではありませんでした。", 4),
    ("レジ対応はまずまずでした。特に問題なく、商品を迅速に処理してくれましたが、笑顔が少なく感じました。価格に見合ったサービスだったかなと思いますが、もう少し親しみやすさがあれば良かったです。", 3),
    ("スタッフの対応は悪くはなかったのですが、ちょっと待たされたので、もう少しスムーズに接客が進めばいいと思います。値段に対しては特に問題なかったのですが、接客のスピードがもう少し速ければ、もっと快適に買い物できたかもしれません。", 3),
    ("レジでの対応は丁寧でしたが、少し時間がかかってしまいました。価格に見合ったサービスだとは思いますが、もう少し速ければ、より満足度が高くなったのではないかと感じました。", 3),
    ("価格は他と比べて平均的で、商品自体の質も悪くはありませんでした。ただ、レジでの対応が少し遅かったり、サービスにもう少し工夫が欲しかったと感じる場面がありました。価格に対しては満足していますが、より良い体験を期待してしまいました。", 3),
    ("スタッフの対応が遅かったです。何度か質問をしたのですが、すぐに答えてもらえなかったり、他のスタッフに確認する必要があったり。価格は問題ないですが、もう少しスムーズな接客が欲しいと思いました。", 3),
    ("レジで少し待たされましたし、対応も少し冷たかったです。お店の価格自体は悪くないですが、もう少し快適なレジ対応があれば、もっとリピーターになると思います。", 3),
    ("価格はそこまで悪くないのですが、商品の質やサービスがその価格に見合っているとは言い切れません。特に接客がもう少し丁寧でスムーズだったら、全体的にもっと満足感が高かったと思います。", 3),
    ("レジでの対応が本当に最悪でした。すごく遅い上に、スタッフは無愛想で、全然笑顔もなく、イライラしました。価格も高いし、サービスがあまりにも酷すぎて二度と行きたくないです。", 1),
    ("価格に対してサービスが全く見合っていません。商品が高いだけで、質も悪く、接客も最悪でした。こんなに悪い体験をしたのは初めてで、他の店舗と比較しても最悪です。二度と行かないと思います。", 1),
    ("店員さんがとても親切でした。困っているとすぐに気づいて、丁寧に説明してくれました。あんなに親身に対応してもらえたのは初めてで、感動しました！", 5),
    ("店員が非常にわかりやすく案内してくれたので、迷うことなく買い物できました。店舗の内装も清潔で、スタッフが常に気を配っている感じが伝わってきました。", 4),
    ("店員が笑顔で、どんな質問にも丁寧に答えてくれたので、とても快適に過ごせました。すごく心地よい買い物ができて、次もここで買い物しようと思います。", 4),
    ("店員は親切に対応してくれましたが、もう少し早く答えてもらえるともっと良かったです。ただ、全体的に良い印象を受けました。", 4),
    ("店員の案内はわかりやすく、すぐに目的の場所にたどり着けました。少しだけ不安そうな顔をしていたのが気になりましたが、親切さは感じました。", 4),
    ("従業員はしっかり説明してくれましたが、少しだけ機械的な感じもしました。でも、対応自体は悪くなかったので、全体的には問題なく買い物できました。", 4),
    ("従業員は親切でしたが、少し冷たい感じがしました。質問には答えてくれましたが、もう少し親身になってくれるとさらに良かったと思います。", 4),
    ("お店の人は簡単な説明をしてくれましたが、もう少し詳しく説明してくれたらよかったです。それでも、特に大きな問題はありませんでした。", 3),
    ("店員は悪くはないのですが、少し素っ気ない感じがしました。もう少し笑顔で接してくれると、もっと良い買い物ができたかなと思います。", 3),
    ("店員に質問したのですが、少しだけ対応が遅くて、少し不安になりました。でも、最終的には答えてくれたので、大きな問題ではありませんでした。", 3),
    ("店員が案内してくれましたが、ちょっと不親切に感じた瞬間がありました。それでも、全体的には特に大きな問題ではありませんでした。", 3),
    ("店員の態度はまあまあでしたが、もう少し明るくて親切だったらよかったかなと思います。それでも、問題なく買い物できたので、悪くはなかったです。", 3),
    ("店員は質問には答えてくれたものの、少し無愛想に感じました。もう少し丁寧に対応してもらえたら、もっと気持ちよく買い物できたと思います。", 2),
    ("店員が少し説明が足りなかった気がします。何度か確認することになり、少し手間取ってしまいました。もう少し親切に案内してくれるとよかったと思います。", 3),
    ("店員の態度は少し冷たかったです。簡単に説明はしてくれたものの、もう少し温かみがあればもっと快適に買い物できたかなと思います。", 2),
    ("質問しても全然答えてくれず、無視されているような気分になりました。最終的にはスタッフがすれ違って通り過ぎただけで、全く助けてもらえませんでした。", 3),
    ("店員は全く協力的ではなく、説明が全く足りませんでした。迷ったまま店内をぐるぐる回る羽目になり、結局スタッフに頼らずに自力で探し出しました。", 3),
    ("最初から最後まで無愛想で、まるで私たちを邪魔者のように扱われました。サービスがあまりにも酷かったので、もう二度とこの店には行きたくないです。", 1),

    # ── 店舗設備・環境 ────────────────────────────────────
    ("店内はとても広々としていて、通路も広くて歩きやすかったです。商品が綺麗に陳列されていて、どこに何があるかが一目でわかり、とても快適に買い物できました！", 5),
    ("トイレは不潔ではないものの、清掃が行き届いておらず、少し不快感を感じました。イートインスペースもテーブルが汚れていて、清潔さが欠けていたので、もう少し気を使ってほしいと思いました。", 2),
    ("駐車場はゴミだらけで、全く清掃されていないような状態でした。駐車スペースも不規則に配置されていて、非常に使いづらかったです。アクセスには問題があったわけではありませんが、施設の管理がひどくてがっかりしました。", 1),
    ("駐車場が広く、清掃も行き届いていました。車を停めるスペースも多く、周囲が整備されていて、気持ちよく訪れることができました。", 4),
    ("店内はきれいに整理されていて、通路も十分に広かったです。ただ、少し商品が散らかっている場所もあったので、もう少し気を使ってほしいとは思いました。", 3),
    ("トイレは清潔でしたが、少し混雑していたので、もう少し頻繁に掃除がされるとさらに良いと思います。イートインスペースは快適で、食事するには十分な環境でした。", 4),
    ("駐車場は広めで、清潔感もありました。ただ、駐車場の一部にもう少し整理整頓が必要な部分があり、そこが少し気になりました。", 3),
    ("店内は比較的きれいに整頓されていましたが、少し混雑していて通路が狭く感じることがありました。商品は見やすかったですが、もう少し広くしてくれるとありがたいです。", 3),
    ("トイレは悪くはないですが、少し清掃が行き届いていない部分もありました。イートインスペースも普通で、特に問題はなかったけれど、もっと清潔感を感じられれば良かったと思います。", 3),
    ("駐車場は広めで便利でしたが、少し汚れている部分も見受けられました。アクセスは良かったですが、駐車場がもっと清潔で整理されているともっと良かったです。", 3),
    ("通路が少し狭く感じ、商品を選ぶ際に他のお客さんとぶつかりそうになることがありました。陳列は整理されているものの、もう少し広々としたスペースがあるともっと快適に感じられると思います。", 3),
    ("トイレは清潔でしたが、ちょっと混雑していたせいか、あまり清潔感が感じられませんでした。イートインスペースも整っていましたが、少し雑然としていて、もっと落ち着いた雰囲気があれば良かったと思います。", 3),
    ("駐車場は便利ですが、少し散らかっている感じがしました。車の通行には問題ありませんが、もう少し清掃や整理が行き届いていれば、より良い印象を受けたと思います。", 4),
    ("店内の通路はやや狭く、商品があまり整理されていないと感じました。混雑している時間帯には歩きづらく、買い物がしにくかったです。改善してほしいです。", 2),
    ("トイレは不潔ではないものの、清掃が行き届いておらず、少し不快感を感じました。イートインスペースもテーブルが汚れていて、清潔さが欠けていたので、もう少し気を使ってほしいと思いました。", 2),
    ("駐車場は広いものの、ゴミが散乱している部分があり、あまり気分よく停めることができませんでした。アクセスには問題ないですが、もっと清掃が行き届いていれば良かったです。", 2),
    ("店内は散らかっていて、通路も狭く、商品がごちゃごちゃに積まれている状態でした。歩くたびに他のお客さんとぶつかりそうになり、非常に不快でした。整頓されていない感じが強く、もう二度と行きたくないです。", 1),
    ("トイレは本当に汚く、全く清掃されていないような状態でした。臭いがひどくて、使うのを避けたくなるくらいでした。イートインスペースも汚れていて、座る気にもなりませんでした。", 1),

    # ── その他 ──────────────────────────────────────────
    ("特に不満はありませんでした。", 4),
    ("スタッフの対応に満足しました。", 4),
    ("レジのもう少し待ち時間が短いと嬉しいです。", 3),
    ("店内が清潔で安心できました。", 4),
    ("商品の品揃えが豊富でした。", 4),
    ("店舗アクセスが便利でした。", 4),
    ("全体的に価格が少し高いと感じました。", 2),
    ("商品の場所がわからなくてお店の人に質問したら、丁寧に対応してくれて助かりました。", 4),
    ("店内は綺麗だし、お店の人も気持ちいい対応してくれて良いですね。また利用したいと思います。", 5),
]

# Spark DataFrameに変換
reviews_master_df = spark.createDataFrame(
  pd.DataFrame(reviews_with_rating, columns=["comment", "rating"])
)

# COMMAND ----------

# DBTITLE 1,フィードバックデータの生成
import pandas as pd
import numpy as np

# reviews_master_df, feedbacksはSpark DataFrame想定
# まずPandas DataFrameに変換
reviews_pd = reviews_master_df.toPandas()
feedbacks_pd = feedbacks_pre.toPandas()

# 各ratingごとに処理
result_list = []

for rating, fb_group in feedbacks_pd.groupby('rating'):
    # 該当ratingのレビューコメント一覧
    rv_group = reviews_pd[reviews_pd['rating'] == rating].copy()
    rv_comments = rv_group['comment'].tolist()
    n_reviews = len(rv_comments)
    n_feedbacks = len(fb_group)
    
    # コメントが足りない場合は繰り返し、余る場合はシャッフルして余りを使わない
    if n_reviews == 0:
        assigned_comments = [np.nan] * n_feedbacks
    else:
        repeats = (n_feedbacks + n_reviews - 1) // n_reviews  # 必要な繰り返し回数
        assigned_comments = (rv_comments * repeats)[:n_feedbacks]
        np.random.shuffle(assigned_comments)  # 割り当て順もシャッフル

    fb_group = fb_group.copy()
    # fb_group['comment_review'] = assigned_comments
    fb_group['comment'] = assigned_comments
    result_list.append(fb_group)

# Pandas DataFrameを作成
merged_data = pd.concat(result_list, ignore_index=True)

# Pandas DataFrameからSpark DataFrameへ変換
feedbacks = spark.createDataFrame(merged_data)

# 結果表示（データフレームのサイズによっては表示が重くなる可能性があるため、小さなサンプルで表示）
print(feedbacks.count())
print(feedbacks.columns)
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

# DBTITLE 1,gold_feedbacksテーブル用CSVダウンロードfromGithub(shortcut ver)
import requests
import os
from concurrent.futures import ThreadPoolExecutor

# gold_feedbacksテーブル用のCSVをGithubからボリュームにダウンロードする関数
class DBDemos:
    @staticmethod
    def download_file_from_git(dest, owner, repo, path):
        def download_file(url, destination):
            local_filename = url.split('/')[-1]
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                print(f'Saving {destination}/{local_filename}')
                with open(f'{destination}/{local_filename}', 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

        if not os.path.exists(dest):
            os.makedirs(dest)

        api_url = f'https://api.github.com/repos/{owner}/{repo}/contents{path}'
        files = requests.get(api_url).json()
        download_urls = [f['download_url'] for f in files if isinstance(f, dict) and 'download_url' in f]

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(lambda url: download_file(url, dest), download_urls)

# ダウンロード実行
DBDemos.download_file_from_git(
    dest=f"/Volumes/{catalog}/{schema}/{volume}",
    owner="komae5519pv",
    repo="komae_dbdemos",
    path="/bootcamp_20250527/data/"
)

# COMMAND ----------

# DBTITLE 1,gold_feedbacksテーブルの生成(shortcut ver)
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, LongType, FloatType
)

# gold_feedback テーブルのスキーマ定義
col_schema = StructType([
    StructField("feedback_id", LongType(), True),      # フィードバックID (bigint)
    StructField("user_id", LongType(), True),          # users.user_id (bigint)
    StructField("product_id", LongType(), True),       # products.product_id (bigint)
    StructField("rating", FloatType(), True),          # 1〜5 (float)
    StructField("date", DateType(), True),             # フィードバック日 (date)
    StructField("category", StringType(), True),       # 種別 (string)
    StructField("summary", StringType(), True),        # 要約 (string)
    StructField("positive_score", FloatType(), True),  # 0.00〜1.00 (float)
    StructField("comment", StringType(), True)         # コメント本文 (string)
])

# gold_feedback テーブル作成
csv_path = f"/Volumes/{catalog}/{schema}/{volume}/gold_feedback.csv"  # ファイル名まで
df = (
    spark.read.format("csv")
         .option("header", "true")
         .option("quote", '"')
         .option("escape", '"')
         .option("multiLine", "true")
         .schema(col_schema)
         .load(csv_path)
)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.gold_feedbacks"
)

print(df.count())
print(df.columns)   # カラム確認
display(df.limit(100))

# COMMAND ----------

# DBTITLE 1,gold_feedbacksテーブルの生成(ai_query)
# print("顧客レビューデータの感情スコアリング・分類・要約します...")
# spark.sql(f'''
# CREATE OR REPLACE TABLE {catalog}.{schema}.gold_feedbacks
# SELECT
#   CAST(feedback_id AS BIGINT) AS feedback_id,
#   CAST(user_id AS BIGINT) AS user_id,
#   CAST(product_id AS BIGINT) AS product_id,
#   CAST(rating AS FLOAT) AS rating,
#   CAST(date AS DATE) AS date,
#   -- カテゴリ
#   ai_query(
#     'databricks-llama-4-maverick',
#     CONCAT(
#       "[指示]次の顧客レビュー内容を、次のカテゴリのいずれかに分類してください",
#       "\n[顧客レビュー]" || comment,
#       "\n[分類カテゴリ]",
#       "\n品揃え・在庫",
#       "\n品質",
#       "\nコスパ・お得感",
#       "\n接客・サービス",
#       "\n店舗設備・環境",
#       "\nその他",
#       "\n[厳守事項]",
#       "\n * カテゴリから1つのみ選択してください。",
#       "\n * カテゴリのみ出力してください。補足は一切不要です。"
#     ), failOnError => False
#   ).result AS category,
#   -- 要約
#   ai_query(
#     'databricks-llama-4-maverick',
#     CONCAT(
#       "[指示]次の顧客レビューから要点を絞って、明快で簡潔な一つの文章に要約して下さい",
#       "\n[顧客レビュー]" || comment,
#       "\n[厳守事項]",
#       "\n * 要約結果のみ出力してください。こちらの指示に関する補足は一切不要です。",
#       "\n * 30文字以内に収めること。"
#     ), failOnError => False
#   ).result AS summary,
#   -- ポジティブスコア
#   CAST( 
#     ai_query(
#         'databricks-llama-4-maverick',
#         CONCAT(
#         "[指示]次の顧客レビュー内容について、0~1の間でポジティブスコアを付与してください",
#         "\n[顧客レビュー]" || comment,
#         "\n[出力形式]",
#         "\n * 範囲0~1の少数第二位までで出力してください。",
#         "\n * 1に近いほどポジティブ度合いが強く、0に近いほどポジティブ度合いが弱い。",
#         "\n[厳守事項]",
#         "\n * ポジティブスコアのみ出力してください。補足は一切不要です。"
#         ), failOnError => False
#     ).result AS FLOAT) AS positive_score,
#   comment
# FROM {catalog}.{schema}.feedbacks
# ''')
# print("顧客レビューデータの感情スコアリング・分類・要約が完了しました！")

# COMMAND ----------

# DBTITLE 1,gold_feedbacksテーブルのメタデータ編集
# MAGIC %sql
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN feedback_id COMMENT "フィードバックID";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN user_id COMMENT "ユーザーID: usersテーブルのuser_idとリンクする外部キー";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN product_id COMMENT "商品ID";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN rating COMMENT "評価: 1～5";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN date COMMENT "フィードバック日";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN comment COMMENT "コメント";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN category COMMENT "フィードバック種別: 品揃え・在庫, 品質, コスパ・お得感, 接客・サービス, 店舗設備・環境, その他";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN positive_score COMMENT "ポジティブスコア: 0.00~1.00で表現";
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN summary COMMENT "フィードバックの要約";
# MAGIC COMMENT ON TABLE gold_feedbacks IS '**gold_feedbacks テーブル**\nユーザーからのフィードバックを管理するテーブルです。\n- 商品やサービスに対するコメント、評価(1～5)、フィードバック日,
# MAGIC カテゴリやポジティブスコア、フィードバックの要約などを保持\n- ユーザー満足度の把握や改善点の分析、優先度付けに役立ちます';

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
# MAGIC --------------
# MAGIC -- 既存削除
# MAGIC --------------
# MAGIC -- PK削除
# MAGIC ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pk;
# MAGIC ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_pk;
# MAGIC ALTER TABLE products DROP CONSTRAINT IF EXISTS products_pk;
# MAGIC ALTER TABLE feedbacks DROP CONSTRAINT IF EXISTS feedbacks_pk;
# MAGIC ALTER TABLE gold_user DROP CONSTRAINT IF EXISTS gold_user_pk;
# MAGIC ALTER TABLE gold_feedbacks DROP CONSTRAINT IF EXISTS gold_feedbacks_pk;
# MAGIC
# MAGIC -- FK削除
# MAGIC ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_users_fk;
# MAGIC ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_products_fk;
# MAGIC ALTER TABLE feedbacks DROP CONSTRAINT IF EXISTS feedbacks_users_fk;
# MAGIC ALTER TABLE feedbacks DROP CONSTRAINT IF EXISTS feedbacks_products_fk;
# MAGIC ALTER TABLE gold_feedbacks DROP CONSTRAINT IF EXISTS gold_feedbacks_users_fk;
# MAGIC ALTER TABLE gold_feedbacks DROP CONSTRAINT IF EXISTS gold_feedbacks_products_fk;
# MAGIC
# MAGIC --------------
# MAGIC -- 新規追加
# MAGIC --------------
# MAGIC -- NULL制約追加
# MAGIC ALTER TABLE users ALTER COLUMN user_id SET NOT NULL;
# MAGIC ALTER TABLE transactions ALTER COLUMN transaction_id SET NOT NULL;
# MAGIC ALTER TABLE products ALTER COLUMN product_id SET NOT NULL;
# MAGIC ALTER TABLE feedbacks ALTER COLUMN feedback_id SET NOT NULL;
# MAGIC ALTER TABLE gold_user ALTER COLUMN user_id SET NOT NULL;
# MAGIC ALTER TABLE gold_feedbacks ALTER COLUMN feedback_id SET NOT NULL;
# MAGIC
# MAGIC -- PK追加
# MAGIC ALTER TABLE users ADD CONSTRAINT users_pk PRIMARY KEY (user_id);
# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_pk PRIMARY KEY (transaction_id);
# MAGIC ALTER TABLE products ADD CONSTRAINT products_pk PRIMARY KEY (product_id);
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_pk PRIMARY KEY (feedback_id);
# MAGIC ALTER TABLE gold_user ADD CONSTRAINT gold_user_pk PRIMARY KEY (user_id);
# MAGIC ALTER TABLE gold_feedbacks ADD CONSTRAINT gold_feedbacks_pk PRIMARY KEY (feedback_id);
# MAGIC
# MAGIC -- FK追加
# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_users_fk FOREIGN KEY (user_id) REFERENCES users (user_id) NOT ENFORCED;
# MAGIC ALTER TABLE transactions ADD CONSTRAINT transactions_products_fk FOREIGN KEY (product_id) REFERENCES products (product_id) NOT ENFORCED;
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_users_fk FOREIGN KEY (user_id) REFERENCES users (user_id) NOT ENFORCED;
# MAGIC ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_products_fk FOREIGN KEY (product_id) REFERENCES products (product_id) NOT ENFORCED;
# MAGIC ALTER TABLE gold_feedbacks ADD CONSTRAINT gold_feedbacks_users_fk FOREIGN KEY (user_id) REFERENCES users (user_id) NOT ENFORCED;
# MAGIC ALTER TABLE gold_feedbacks ADD CONSTRAINT gold_feedbacks_products_fk FOREIGN KEY (product_id) REFERENCES products (product_id) NOT ENFORCED;

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
    spark.sql(f"ALTER TABLE gold_feedbacks SET TAGS ('{certified_tag}')")
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
