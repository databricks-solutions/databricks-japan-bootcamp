-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near '(': missing ')'. SQLSTATE: 42601 (line 12, pos 23)

== SQL ==
EXPLAIN -- Synapse Dedicated SQL Pool: order_items table
-- Hash on OrderID to co-locate with orders during joins

CREATE OR REPLACE TABLE dbo.order_items
(
    OrderID         BIGINT          NOT NULL,
    LineNumber      INT             NOT NULL,
    ProductID       INT             NOT NULL,
    Quantity        INT             NOT NULL,
    UnitPrice       DECIMAL(18,2)   NOT NULL,
    DiscountAmount  DECIMAL(18,2)   NOT NULL DEFAULT 0,
    LineAmount      AS (Quantity * UnitPrice - DiscountAmount) PERSISTED
-----------------------^^^
)
;

*/

 ---------------Exception End --------------------
