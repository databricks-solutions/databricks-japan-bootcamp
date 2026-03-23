from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.materialized_view(name="revenue_by_subcategory")
def revenue_by_subcategory():
  return (
    spark.read.table("transactions_enriched")
    .groupBy("subcategory")
    .agg(F.sum("transaction_price").alias("sum_revenue"))
  )