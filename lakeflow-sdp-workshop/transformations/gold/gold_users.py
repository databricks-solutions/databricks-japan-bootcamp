# from pyspark import pipelines as dp
# from pyspark.sql import functions as F

# @dp.materialized_view(name="gold_user")
# def user_metrics():
#     return (
#         spark.read.table("transactions_enriched").alias("u")
#         .join(
#             spark.read.table("transactions").alias("t"),
#             "user_id",
#             "left"
#         )
#         .join(
#             spark.read.table("products").alias("p"),
#             "product_id",
#             "left"
#         )
#         .groupBy("u.user_id", "u.age")
#         .agg(
#             F.expr("CASE WHEN u.age < 35 THEN '若年層' WHEN u.age < 55 THEN '中年層' ELSE 'シニア層' END").alias("age_group"),
#             F.sum(F.expr("CASE WHEN p.category = '食料品' THEN t.quantity ELSE 0 END")).alias("food_quantity"),
#             F.sum(F.expr("CASE WHEN p.category = '日用品' THEN t.quantity ELSE 0 END")).alias("daily_quantity"),
#             F.sum(F.expr("CASE WHEN p.category NOT IN ('食料品', '日用品') THEN t.quantity ELSE 0 END")).alias("other_quantity")
#         )
#     )

# @dp.materialized_view(name="gold_user")
# def gold_user():
#     return (
#         spark.read.table("users")
#         .join(spark.read.table("user_metrics"), "user_id")
#     )