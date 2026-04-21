# Databricks notebook source
# Code converted on 2026-04-21 20:05:28
import os
import oracledb
from pyspark.sql import *
from pyspark.sql.functions import *
from pyspark import SparkContext
from pyspark.sql.functions import lit, to_timestamp, when, expr, col, explode, count, current_date


# COMMAND ----------
# Variable_declaration_comment

dbutils.widgets.text(name = 'run_date', defaultValue = '')
run_date = dbutils.widgets.get("run_date")

dbutils.widgets.text(name = 'env_db', defaultValue = '')
env_db = dbutils.widgets.get("env_db")

dbutils.widgets.text(name = 'src_customers_table', defaultValue = 'SOURCE_CUSTOMERS')
src_customers_table = dbutils.widgets.get("src_customers_table")

dbutils.widgets.text(name = 'tgt_customers_table', defaultValue = 'TARGET_CUSTOMERS')
tgt_customers_table = dbutils.widgets.get("tgt_customers_table")

dbutils.widgets.text(name = 'env_db_server', defaultValue = '')
env_db_server = dbutils.widgets.get("env_db_server")

dbutils.widgets.text(name = 'env_db_user', defaultValue = '')
env_db_user = dbutils.widgets.get("env_db_user")

dbutils.widgets.text(name = 'env_db_password', defaultValue = '')
env_db_password = dbutils.widgets.get("env_db_password")

dbutils.widgets.text(name = 'env_db_schema', defaultValue = '')
env_db_schema = dbutils.widgets.get("env_db_schema")

# COMMAND ----------
# Processing node L_Src_Tgt, type SOURCE
# COLUMN COUNT: 6
# Original node name Source_DB, link L_Src_Tgt
L_Src_Tgt = spark.sql(f"""SELECT
file_date,
customer_code AS customer_id,
sequence_no,
branch_code,
amount,
status_code
FROM #env.db_schema#.{src_customers_table} 
WHERE  customer_code.isNotNull()
AND      sequence_no.isNotNull()
AND      branch_code.isNotNull()""")


# COMMAND ----------
# Processing node Target_DB, type TARGET
# COLUMN COUNT: 6

Target_DB = L_Src_Tgt.select(
	L_Src_Tgt.customer_id.alias('customer_id'),
	L_Src_Tgt.sequence_no.alias('sequence_no'),
	L_Src_Tgt.branch_code.alias('branch_code'),
	L_Src_Tgt.amount.alias('amount'),
	L_Src_Tgt.status_code.alias('status_code'),
	L_Src_Tgt.file_date.alias('file_date')
)
Target_DB.write.saveAsTable('#env.db_schema#.{tgt_customers_table}', mode = 'append')
