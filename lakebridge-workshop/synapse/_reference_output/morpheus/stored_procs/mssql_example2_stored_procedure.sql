-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near ';'. SQLSTATE: 42601 (line 13, pos 72)

== SQL ==
EXPLAIN CREATE
    PROCEDURE
    `dbo`.`DEMO_FORECAST_OUTLIER_CHECK_UPDATE`(
        IN _SchemaName VARCHAR(128), IN _OutlierMultiplier DECIMAL(5, 2) DEFAULT 1.3
    )
    LANGUAGE SQL
    SQL SECURITY INVOKER
    AS
        BEGIN
            DECLARE _Result INT = 0;
            DECLARE _ErrorMsg STRING;
            DECLARE _CurrentDate DATE;
            DECLARE _ErrorProcName VARCHAR(128) = /* OBJECT_NAME(...) */;
------------------------------------------------------------------------^^^
            -- FIXME: Function OBJECT_NAME is not convertible to Databricks SQL
            CREATE TEMPORARY TABLE `#TEMP_OUTLIER_INFO` (LocationId VARCHAR(10), OutlierThreshold DECIMAL(8, 2));
            BEGIN
                DECLARE _RaiseArgs MAP<STRING, STRING>;
                DECLARE EXIT HANDLER FOR USER_RAISED_EXCEPTION
                BEGIN
                    DECLARE _ThrowArgs MAP<STRING, STRING>;
                    DECLARE _errorCond STRING;
                    DECLARE _sqlState STRING;
                    DECLARE _errorLine INT;
                    DECLARE _errorProc STRING;
                    GET DIAGNOSTICS CONDITION 1
                    _ThrowArgs = MESSAGE_ARGUMENTS,
                    _errorCond = CONDITION_IDENTIFIER,
                    _sqlState = RETURNED_SQLSTATE,
                    _errorLine = LINE_NUMBER;
                    SET _ThrowArgs = from_json(_ThrowArgs['errorMessage'], 'MAP<STRING, STRING>');
                    SET _ThrowArgs = IF(element_at(_ThrowArgs, 'ERROR_STATE') IS NULL, map_concat(_ThrowArgs, map('ERROR_STATE', _sqlState)), _throwArgs);
                    SET _ThrowArgs = IF(element_at(_ThrowArgs, 'ERROR_MESSAGE') IS NULL, map_concat(_ThrowArgs, map('ERROR_MESSAGE', 'No message provided.')), _throwArgs);
                    SET _ThrowArgs = IF(element_at(_ThrowArgs, 'ERROR_SEVERITY') IS NULL, map_concat(_ThrowArgs, map('ERROR_SEVERITY', '16')), _throwArgs);
                    SET _errorProc = 'ERROR_PROCEDURE is not supported in Databricks SQL.';
                    SET _Result = 2;
                    SET _ErrorMsg = _ThrowArgs['ERROR_MESSAGE'];
                    -- FIXME: Databricks does not support PRINT: PRINT('Error: ' + @ErrorMsg)
                    
                    IF (@@TRANCOUNT() > 0) THEN
                        ROLLBACK TRANSACTION;
                    END IF;
                    CALL `dbo`.`LogError`(_ErrorProcName AS _ProcName, _ErrorMsg AS _ErrorMessage);
                    SELECT raise_error(to_json(_ThrowArgs));
                END;
                BEGIN TRANSACTION;
                DECLARE _SQL STRING;
                SET
                _SQL
                =
                '
            SELECT @CurrentDateOut = SystemDate
            FROM '||
                '"'||
                REGEXP_REPLACE(_SchemaName, '"', '""')||
                '"'||
                '.SystemDateTable;
        ';
                CALL sp_executesql(_SQL, '@CurrentDateOut DATE OUTPUT', _CurrentDate AS _CurrentDateOut);
                SET
                _SQL
                =
                '
            INSERT INTO #TEMP_OUTLIER_INFO (LocationId, OutlierThreshold)
            SELECT
                d.LocationId,
                CONVERT(DECIMAL(8,2),
                    PERCENTILE_CONT(0.99)
                    WITHIN GROUP (ORDER BY d.MetricValue)
                    OVER (PARTITION BY d.LocationId)
                )
            FROM '||
                '"'||
                REGEXP_REPLACE(_SchemaName, '"', '""')||
                '"'||
                '.HistoricalDataTable d
            WHERE CONVERT(DATE, d.TargetDate) >= DATEADD(YEAR, -1, @CurrentDateParam)
        ';
                CALL sp_executesql(_SQL, '@CurrentDateParam DATE', _CurrentDate AS _CurrentDateParam);
                SET
                _SQL
                =
                '
            UPDATE f
            SET f.OriginalForecastValue = f.ForecastValue
            FROM '||
                '"'||
                REGEXP_REPLACE(_SchemaName, '"', '""')||
                '"'||
                '.ForecastTable f
            INNER JOIN #TEMP_OUTLIER_INFO t ON f.LocationId = t.LocationId
            WHERE CONVERT(DATE, f.ForecastDate) = @CurrentDateParam
              AND f.ForecastValue > t.OutlierThreshold * @Multiplier
        ';
                CALL
                sp_executesql(
                    _SQL,
                    '@CurrentDateParam DATE, @Multiplier DECIMAL(5,2)',
                    _CurrentDate AS _CurrentDateParam,
                    _OutlierMultiplier AS _Multiplier
                );
                SET
                _SQL
                =
                '
            UPDATE f
            SET f.ForecastValue = t.OutlierThreshold * @Multiplier
            FROM '||
                '"'||
                REGEXP_REPLACE(_SchemaName, '"', '""')||
                '"'||
                '.ForecastTable f
            INNER JOIN #TEMP_OUTLIER_INFO t ON f.LocationId = t.LocationId
            WHERE CONVERT(DATE, f.ForecastDate) = @CurrentDateParam
              AND f.ForecastValue > t.OutlierThreshold * @Multiplier
        ';
                CALL
                sp_executesql(
                    _SQL,
                    '@CurrentDateParam DATE, @Multiplier DECIMAL(5,2)',
                    _CurrentDate AS _CurrentDateParam,
                    _OutlierMultiplier AS _Multiplier
                );
                COMMIT TRANSACTION;
            END;
            RETURN _Result;
        END;

*/

 ---------------Exception End --------------------
