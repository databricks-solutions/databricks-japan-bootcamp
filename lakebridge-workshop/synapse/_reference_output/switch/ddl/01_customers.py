# Databricks notebook source
# MAGIC %md
# MAGIC # 01_customers
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/ddl/01_customers.sql`
# COMMAND ----------
# COMMAND ----------
# Create customers table with Delta Lake
spark.sql("""
CREATE TABLE IF NOT EXISTS customers (
    CustomerID LONG NOT NULL,
    CustomerName STRING NOT NULL,
    Email STRING,
    PhoneNumber STRING,
    BirthDate DATE,
    Gender STRING,
    RegisteredAt TIMESTAMP NOT NULL,
    LastUpdatedAt TIMESTAMP NOT NULL,
    IsActive BOOLEAN NOT NULL
)
USING DELTA
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
