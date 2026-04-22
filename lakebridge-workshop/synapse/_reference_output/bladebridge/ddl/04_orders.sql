-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near ';': extra input ';'. SQLSTATE: 42601 (line 13, pos 69)

== SQL ==
EXPLAIN -- Synapse Dedicated SQL Pool: orders table
-- Large fact table partitioned by OrderDate (monthly) and hashed on CustomerID

CREATE OR REPLACE TABLE dbo.orders
(
    OrderID         BIGINT          NOT NULL,
    CustomerID      BIGINT          NOT NULL,
    StoreID         INT             NOT NULL,
    OrderDate       DATE            NOT NULL,
    OrderStatus STRING     NOT NULL,
    TotalAmount     DECIMAL(18,2)   NOT NULL,
    TaxAmount       DECIMAL(18,2)   NOT NULL,
    CreatedAt       timestamp    NOT NULL DEFAULT current_timestamp();)
---------------------------------------------------------------------^^^
;

*/

 ---------------Exception End --------------------
