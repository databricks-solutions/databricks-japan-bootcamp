# # このファイルのコードはワークショップの途中、データ品質についての実験でコメントアウトします

# from pyspark import pipelines as dp

# # パラメータとして設定したカタログ名とスキーマ名を取得
# catalog_name = spark.conf.get("catalog_name")
# schema_name = spark.conf.get("schema_name")

# backfill_dir = f"/Volumes/{catalog_name}/{schema_name}/raw_data/users_backfill/"

# def setup_subscriber_backfill_flow(backfill_dir):
#     # 顧客マスターのChange Data Feed (CDF)を読み込んで一時的なビューにする
#     @dp.view(name="users_backfill")
#     def users_backfill():
#         return (
#           spark.readStream.format("cloudFiles")
#           .option("cloudFiles.format", "csv")
#           .option("cloudFiles.inferColumnTypes", "true")
#           .option("cloudFiles.rescuedDataColumn", "_rescued_data_subscriber")
#           .load(backfill_dir)
#         )
#     # AutoCDCを使って、顧客のCDFに基づいて顧客マスターを差分更新する
#     dp.create_auto_cdc_flow(
#       name=f"users_auto_cdc_backfill",
#       target="users",
#       source="users_backfill",
#       keys=["user_id"],
#       sequence_by="last_updated",
#       apply_as_deletes="operation='DELETE'",
#       except_column_list = ["operation"],
#       stored_as_scd_type=1,
#       # 一回だけ実行する
#       once=True
#     )

# setup_subscriber_backfill_flow(backfill_dir)