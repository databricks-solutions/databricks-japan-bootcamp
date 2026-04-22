-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near ';'. SQLSTATE: 42601 (line 7, pos 35)

== SQL ==
EXPLAIN -- ==========================================
-- T-SQL EXAMPLE #2: Stored Procedure with Outlier Checking
-- ==========================================

CREATE OR REPLACE PROCEDURE `dbo`.`DEMO_FORECAST_OUTLIER_CHECK_UPDATE`(
IN V_SchemaName STRING,
IN V_OutlierMultiplier DECIMAL(5,2); DEFAULT 1.30)
-----------------------------------^^^
LANGUAGE SQL
SQL SECURITY INVOKER
AS

BEGIN

    
DECLARE VARIABLE V_Result           INT           ;

DECLARE VARIABLE V_ErrorMsg STRING;
DECLARE VARIABLE V_CurrentDate      DATE;
DECLARE VARIABLE V_ErrorProcName STRING ;

DECLARE VARIABLE V_SQL STRING;
-- Variable declarations

SET V_Result = 0;
SET V_ErrorProcName = OBJECT_NAME(V_V_PROCID);
-- Create a temporary table to store outlier thresholds

CREATE TEMPORARY TABLE TEMP_TABLE_TEMP_OUTLIER_INFO (
          LocationId STRING,
          OutlierThreshold DECIMAL(8,2)
    );
DECLARE EXIT HANDLER FOR SQLEXCEPTION
BEGIN
GET DIAGNOSTICS CONDITION 1

        ;
SET V_Result = 2;
SET V_ErrorMsg = MESSAGE_TEXT;
SELECT('Error: ' || V_ErrorMsg);
IF (V_V_TRANCOUNT > 0)
            ;
ROLLBACK TRAN FORECAST_OUTLIER_CHECK;
-- Log the error (simplified):

call `dbo`.`LogError`(
            V_ProcName     = V_ErrorProcName,
            V_ErrorMessage = V_ErrorMsg);
        -- Re-throw the error
        SIGNAL SQLSTATE '45000';

END;

TRAN FORECAST_OUTLIER_CHECK;
-- 1) Retrieve current date from a "SystemDateTable" in the given schema

SET V_SQL = '
            SELECT V_CurrentDateOut = SystemDate
            FROM ' || concat('[', V_SchemaName, ']') || '.SystemDateTable;
        ';
CALL
            V_SQL,
            'V_CurrentDateOut DATE ',
            V_CurrentDateOut = V_CurrentDate ;
-- 2) Insert outlier thresholds (99th percentile) from "HistoricalDataTable"

SET V_SQL = '
            INSERT INTO TEMP_TABLE_TEMP_OUTLIER_INFO (LocationId, OutlierThreshold)
            SELECT
                d.LocationId,
                CAST(PERCENTILE_CONT(0.99)
WITHIN GROUP (ORDER BY d.MetricValue)
OVER (PARTITION BY d.LocationId) AS DECIMAL(8,2))
            FROM ' || concat('[', V_SchemaName, ']') || '.HistoricalDataTable d
            WHERE CAST(d.TargetDate AS DATE) >= DATEADD(YEAR, -1, V_CurrentDateParam)
        ';
CALL
            V_SQL,
            'V_CurrentDateParam DATE',
            V_CurrentDateParam = V_CurrentDate;
-- 3) Save original forecast values above threshold in "ForecastTable"

SET V_SQL = '
            MERGE INTO ' || concat('[', V_SchemaName, ']') || '.ForecastTable f
USING (
SELECT * 
FROM ' || concat('[', V_SchemaName, ']') || '.ForecastTable f
INNER JOIN TEMP_TABLE_TEMP_OUTLIER_INFO t ON f.LocationId = t.LocationId
)
ON CAST(f.ForecastDate AS DATE) = V_CurrentDateParam AND f.ForecastValue > t.OutlierThreshold * V_Multiplier '; AND 
COALESCE(f.OriginalForecastValue::string,'__NULL__') = COALESCE(f_TGT.OriginalForecastValue::string,'__NULL__') AND 
COALESCE(f.ForecastValue::string,'__NULL__') = COALESCE(f_TGT.ForecastValue::string,'__NULL__') AND 
COALESCE(f.LocationId::string,'__NULL__') = COALESCE(f_TGT.LocationId::string,'__NULL__') AND 
COALESCE(f.ForecastDate::string,'__NULL__') = COALESCE(f_TGT.ForecastDate::string,'__NULL__')
WHEN MATCHED THEN UPDATE SET
OriginalForecastValue = f.ForecastValue;
CALL
            V_SQL,
            'V_CurrentDateParam DATE, V_Multiplier DECIMAL(5,2)',
            V_CurrentDateParam = V_CurrentDate,
            V_Multiplier = V_OutlierMultiplier;
-- 4) Update outlier values to cap them at threshold * multiplier

SET V_SQL = '
            MERGE INTO ' || concat('[', V_SchemaName, ']') || '.ForecastTable f
USING (
SELECT * 
FROM ' || concat('[', V_SchemaName, ']') || '.ForecastTable f
INNER JOIN TEMP_TABLE_TEMP_OUTLIER_INFO t ON f.LocationId = t.LocationId
)
ON CAST(f.ForecastDate AS DATE) = V_CurrentDateParam AND f.ForecastValue > t.OutlierThreshold * V_Multiplier '; AND 
COALESCE(f.ForecastValue::string,'__NULL__') = COALESCE(f_TGT.ForecastValue::string,'__NULL__') AND 
COALESCE(f.LocationId::string,'__NULL__') = COALESCE(f_TGT.LocationId::string,'__NULL__') AND 
COALESCE(f.ForecastDate::string,'__NULL__') = COALESCE(f_TGT.ForecastDate::string,'__NULL__')
WHEN MATCHED THEN UPDATE SET
ForecastValue = t.OutlierThreshold * V_Multiplier;
CALL
            V_SQL,
            'V_CurrentDateParam DATE, V_Multiplier DECIMAL(5,2)',
            V_CurrentDateParam = V_CurrentDate,
            V_Multiplier = V_OutlierMultiplier;
COMMIT TRAN FORECAST_OUTLIER_CHECK;
-- DROP TABLE IF EXISTS #TEMP_OUTLIER_INFO; -- Temp tables are automatically dropped at the end of the session

RETURN V_Result;
END;

*/

 ---------------Exception End --------------------
