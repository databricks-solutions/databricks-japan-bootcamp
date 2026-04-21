-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near 'expecting'. SQLSTATE: 42601 (line 3, pos 0)

== SQL ==
EXPLAIN -- internal error
-- Multiple errors: Parsing error starting at 19:4 involving rule 'unresolved rule name' and token '('(LPAREN): unexpected extra input '(' while parsing a tableOptions in a CREATE TABLE command in a CREATE command in a DDL command in a sqlCommands
expecting one of: ')', ',', Parsing error starting at 20:18 involving rule 'unresolved rule name' and token 'RANGE'(RANGE): missing ASSIGN at 'RANGE'
^^^
while parsing a sqlCommands, Parsing error starting at 20:24 involving rule 'unresolved rule name' and token 'RIGHT'(RIGHT): unexpected extra input 'RIGHT' while parsing a sqlFile
expecting one of: @Local, End of batch, Identifier, Node ID, Select Statement, Statement, '(', 'ADD', 'ARRAY', 'ATOMIC', 'BULK', 'CALL'...
-- Synapse Dedicated SQL Pool: orders table
-- Large fact table partitioned by OrderDate (monthly) and hashed on CustomerID
CREATE TABLE dbo.orders
(
    OrderID         BIGINT          NOT NULL,
    CustomerID      BIGINT          NOT NULL,
    StoreID         INT             NOT NULL,
    OrderDate       DATE            NOT NULL,
    OrderStatus     VARCHAR(20)     NOT NULL,
    TotalAmount     DECIMAL(18,2)   NOT NULL,
    TaxAmount       DECIMAL(18,2)   NOT NULL,
    CreatedAt       DATETIME2(3)    NOT NULL DEFAULT SYSUTCDATETIME()
)
WITH
(
    DISTRIBUTION = HASH (CustomerID),
    CLUSTERED COLUMNSTORE INDEX,
    PARTITION
    (
        OrderDate RANGE RIGHT FOR VALUES
        (
            '2025-01-01', '2025-04-01', '2025-07-01', '2025-10-01',
            '2026-01-01', '2026-04-01'
        )
    )
);
GO

*/

 ---------------Exception End --------------------
