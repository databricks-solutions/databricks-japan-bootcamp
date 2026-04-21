# Databricks notebook source
# MAGIC %md
# MAGIC # mssql_example2_stored_procedure
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC 
# MAGIC Source script: `/Volumes/<your-catalog>/switch/switch_volume/input-<ts>-<id>/stored_procs/mssql_example2_stored_procedure.sql`
# COMMAND ----------
# COMMAND ----------
# Widgets for parameters
dbutils.widgets.text("SchemaName", "")
dbutils.widgets.text("OutlierMultiplier", "1.30")

# COMMAND ----------
# Convert inputs
schema_name = dbutils.widgets.get("SchemaName")
outlier_multiplier = float(dbutils.widgets.get("OutlierMultiplier"))

# COMMAND ----------
# Initialize result variable
result = 0

# COMMAND ----------
# Create a temporary Delta table for outlier info (using OR REPLACE to avoid conflicts)
spark.sql("""
CREATE OR REPLACE TABLE TEMP_OUTLIER_INFO (
    LocationId STRING,
    OutlierThreshold DECIMAL(8,2)
)
""")

# COMMAND ----------
# Capture the current timestamp for rollback on ForecastTable
try:
    hist_forecast = spark.sql(f"DESCRIBE HISTORY {schema_name}.ForecastTable LIMIT 1").collect()[0]
    restore_ts_forecast = hist_forecast["timestamp"]
except:
    restore_ts_forecast = None

# COMMAND ----------
try:
    # Retrieve the current system date
    current_date_df = spark.sql(f"""
    SELECT SystemDate FROM {schema_name}.SystemDateTable
    """)
    current_date = current_date_df.collect()[0]["SystemDate"]

    # Populate the temporary outlier info table
    # Calculate the 99th percentile of MetricValue per LocationId for the past year
    spark.sql(f"""
    INSERT INTO TEMP_OUTLIER_INFO (LocationId, OutlierThreshold)
    SELECT 
        d.LocationId,
        cast(percentile_cont(0.99) WITHIN GROUP (ORDER BY d.MetricValue) OVER (PARTITION BY d.LocationId) AS DECIMAL(8,2)) AS OutlierThreshold
    FROM {schema_name}.HistoricalDataTable d
    WHERE cast(d.TargetDate AS DATE) >= date_add('{current_date}', -365)
    """)

    # Update OriginalForecastValue for records exceeding the outlier threshold
    # Databricks does not support FROM clause in UPDATE, so use MERGE INTO
    spark.sql(f"""
    MERGE INTO {schema_name}.ForecastTable f
    USING TEMP_OUTLIER_INFO t
    ON f.LocationId = t.LocationId
    WHEN MATCHED AND cast(f.ForecastDate AS DATE) = '{current_date}' 
                 AND f.ForecastValue > t.OutlierThreshold * {outlier_multiplier}
    THEN UPDATE SET f.OriginalForecastValue = f.ForecastValue
    """)

    # Update ForecastValue to capped value for records exceeding the outlier threshold
    spark.sql(f"""
    MERGE INTO {schema_name}.ForecastTable f
    USING TEMP_OUTLIER_INFO t
    ON f.LocationId = t.LocationId
    WHEN MATCHED AND cast(f.ForecastDate AS DATE) = '{current_date}' 
                 AND f.ForecastValue > t.OutlierThreshold * {outlier_multiplier}
    THEN UPDATE SET f.ForecastValue = t.OutlierThreshold * {outlier_multiplier}
    """)

    print("Outlier check and update completed successfully.")

except Exception as e:
    result = 2
    error_msg = str(e)
    print(f"Error: {error_msg}")
    
    # Rollback ForecastTable to previous version if restore timestamp is available
    if restore_ts_forecast is not None:
        spark.sql(f"RESTORE TABLE {schema_name}.ForecastTable TO TIMESTAMP AS OF '{restore_ts_forecast}'")
        print("ForecastTable restored to previous version.")
    
    # Log error (assuming LogError procedure exists; convert to a separate notebook or function call)
    # Example: dbutils.notebook.run("LogError", 60, {"ProcName": "DEMO_FORECAST_OUTLIER_CHECK_UPDATE", "ErrorMessage": error_msg})
    
    # Re-raise the exception
    raise e

finally:
    # Clean up the temporary table
    spark.sql("DROP TABLE IF EXISTS TEMP_OUTLIER_INFO")

# COMMAND ----------
# Return result (0 for success, 2 for error)
dbutils.notebook.exit(str(result))
# COMMAND ----------
# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.
