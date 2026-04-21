# Databricks notebook source
# MAGIC %md
# MAGIC # 03_stores
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/ddl/03_stores.sql`
# COMMAND ----------
# COMMAND ----------
# Create the stores table
# Note: Databricks Delta Lake does not support DISTRIBUTION or HEAP hints from T-SQL
# These are specific to SQL Server/Azure Synapse and are commented out
spark.sql("""
CREATE TABLE IF NOT EXISTS stores (
    StoreID INT NOT NULL,
    StoreName STRING NOT NULL,
    RegionCode STRING NOT NULL,
    PrefectureCode STRING NOT NULL,
    OpenedAt DATE NOT NULL,
    ClosedAt DATE
)
USING DELTA
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
