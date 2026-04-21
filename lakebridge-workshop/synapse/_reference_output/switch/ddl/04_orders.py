# Databricks notebook source
# MAGIC %md
# MAGIC # 04_orders
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/ddl/04_orders.sql`
# COMMAND ----------
# COMMAND ----------
# Create the orders table
# Note: Databricks Delta Lake does not support DISTRIBUTION, CLUSTERED COLUMNSTORE INDEX, or PARTITION syntax from Azure Synapse/SQL DW
# These are commented out with explanations below
spark.sql("""
CREATE TABLE IF NOT EXISTS dbo.orders (
    OrderID LONG NOT NULL,
    CustomerID LONG NOT NULL,
    StoreID INT NOT NULL,
    OrderDate DATE NOT NULL,
    OrderStatus STRING NOT NULL,
    TotalAmount DECIMAL(18,2) NOT NULL,
    TaxAmount DECIMAL(18,2) NOT NULL,
    CreatedAt TIMESTAMP NOT NULL
)
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
