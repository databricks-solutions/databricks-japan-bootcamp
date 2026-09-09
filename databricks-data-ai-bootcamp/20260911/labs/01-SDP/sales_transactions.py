from pyspark import pipelines as dp


@dp.table(
    name="sales_transactions",
    comment="Raw bakery transactions streamed from samples.bakehouse.sales_transactions",
)
def sales_transactions():
    # @dp.table 内の spark.readStream.table(...) ⇒ ストリーミングテーブル
    return spark.readStream.table("samples.bakehouse.sales_transactions")
