from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.materialized_view(name="revenue_by_user_segment")
def revenue_by_user_segment():
  return (
    spark.read.table("transactions_enriched")
    .withColumn("age_group", F.expr("CASE WHEN age < 35 THEN '若年層' WHEN age < 55 THEN '中年層' ELSE 'シニア層' END"))
    .groupBy(["age_group", "gender", "region"])
    .agg(F.sum("transaction_price").alias("sum_revenue"))
  )