# from pyspark import pipelines as dp
# from pyspark.sql import functions as F
# from utilities import expectation_rules

# master_check = expectation_rules.get_master_check_rules()

# # マスターに存在する商品、ユーザーかどうかのデータ品質チェックを適用
# @dp.expect_all_or_fail(master_check)
# @dp.table(name="transactions_enriched")
# def transactions_enriched():
#     return (
#         spark.readStream.table("transactions")
#         .join(spark.read.table("users"), "user_id", "left")
#         .join(spark.read.table("products"), "product_id", "left")
#         .drop()
#     )