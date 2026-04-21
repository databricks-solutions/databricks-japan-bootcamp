# Databricks notebook source
# MAGIC %md
# MAGIC # 02_products
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/ddl/02_products.sql`
# COMMAND ----------
# COMMAND ----------
# Create products table
# Note: Databricks Delta Lake does not support distribution hints or clustered indexes
# These are commented out as they are not applicable in Spark SQL
spark.sql("""
CREATE TABLE IF NOT EXISTS products (
    ProductID INT NOT NULL,
    ProductName STRING NOT NULL,
    CategoryCode STRING NOT NULL,
    UnitPrice DECIMAL(19,4) NOT NULL,
    Barcode STRING,
    LaunchedAt DATE,
    DiscontinuedAt DATE
)
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
