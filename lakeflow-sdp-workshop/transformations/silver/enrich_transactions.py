from pyspark import pipelines as dp
from pyspark.sql import functions as F
from utilities import expectation_rules

@dp.table(name="transactions_enriched")
def transactions_enriched():
    return (
        spark.readStream.table("transactions")
        .join(spark.read.table("users"), "user_id", "left")
        .join(spark.read.table("products"), "product_id", "left")
    )