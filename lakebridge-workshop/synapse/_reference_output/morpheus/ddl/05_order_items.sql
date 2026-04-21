-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near 'ALWAYS'. SQLSTATE: 42601 (line 13, pos 29)

== SQL ==
EXPLAIN CREATE
    /* DISTRIBUTION = HASH (OrderID) CLUSTERED COLUMNSTORE INDEX */
    -- FIXME: ^^^ The above create table options are unsupported
    TABLE dbo.order_items
    (
        OrderID BIGINT NOT NULL,
        LineNumber INT NOT NULL,
        ProductID INT NOT NULL,
        Quantity INT NOT NULL,
        UnitPrice DECIMAL(18, 2) NOT NULL,
        DiscountAmount DECIMAL(18, 2) NOT NULL DEFAULT 0,
        -- Delta Lake generated columns are ALWAYS persisted
        LineAmount GENERATED ALWAYS AS (Quantity * UnitPrice - DiscountAmount)
-----------------------------^^^
    );



CREATE /* STATISTICS stats_order_items_ProductID ON dbo.order_items (ProductID) */;
-- FIXME: TSQL: Databricks SQL has no equivalent to the CREATE STATISTICS command, and it cannot be translated

*/

 ---------------Exception End --------------------
