# Databricks notebook source
# MAGIC %md
# MAGIC # 05_order_items
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/ddl/05_order_items.sql`
# COMMAND ----------
# COMMAND ----------
# Create the order_items table
# Note: Databricks Delta Lake does not support DISTRIBUTION or CLUSTERED COLUMNSTORE INDEX.
# These are specific to Azure Synapse/SQL DW and are commented out.
# Delta Lake automatically handles data distribution and columnar storage.
spark.sql("""
CREATE TABLE IF NOT EXISTS dbo.order_items (
    OrderID LONG NOT NULL,
    LineNumber INT NOT NULL,
    ProductID INT NOT NULL,
    Quantity INT NOT NULL,
    UnitPrice DECIMAL(18,2) NOT NULL,
    DiscountAmount DECIMAL(18,2) NOT NULL DEFAULT 0,
    LineAmount DECIMAL(18,2) GENERATED ALWAYS AS (Quantity * UnitPrice - DiscountAmount)
)
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
