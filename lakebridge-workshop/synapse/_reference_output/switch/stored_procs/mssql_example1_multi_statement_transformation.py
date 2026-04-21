# Databricks notebook source
# MAGIC %md
# MAGIC # mssql_example1_multi_statement_transformation
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/stored_procs/mssql_example1_multi_statement_transformation.sql`
# COMMAND ----------
# COMMAND ----------
# Create Products table with Delta
spark.sql("""
CREATE TABLE IF NOT EXISTS Products (
    ProductID INT,
    ProductName STRING,
    Price DECIMAL(10,2),
    CreatedAt TIMESTAMP
)
""")

# COMMAND ----------
# Insert initial data into Products
spark.sql("""
INSERT INTO Products (ProductID, ProductName, Price, CreatedAt)
VALUES 
    (101, 'Widget A', 12.50, current_timestamp()),
    (102, 'Widget B', 19.99, current_timestamp()),
    (103, 'Widget C', 29.75, current_timestamp())
""")

# COMMAND ----------
# Create temporary Discounts table
spark.sql("""
CREATE OR REPLACE TABLE Discounts (
    ProductID INT,
    DiscountRate DOUBLE
)
""")

# COMMAND ----------
# Insert discount data
spark.sql("""
INSERT INTO Discounts (ProductID, DiscountRate)
VALUES 
    (101, 0.10),
    (103, 0.25)
""")

# COMMAND ----------
# Update Products with discounts using MERGE INTO
spark.sql("""
MERGE INTO Products p
USING Discounts d
ON p.ProductID = d.ProductID
WHEN MATCHED THEN 
    UPDATE SET p.Price = p.Price * (1 - d.DiscountRate)
""")

# COMMAND ----------
# Delete old products not in Discounts using a subquery approach
spark.sql("""
DELETE FROM Products
WHERE CreatedAt < date_add(current_timestamp(), -7)
  AND ProductID NOT IN (SELECT ProductID FROM Discounts)
""")

# COMMAND ----------
# Display final results
final_products = spark.sql("SELECT * FROM Products")
display(final_products)

# COMMAND ----------
# Clean up temporary table
spark.sql("DROP TABLE IF EXISTS Discounts")

# COMMAND ----------
# Drop Products table
spark.sql("DROP TABLE IF EXISTS Products")
# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
