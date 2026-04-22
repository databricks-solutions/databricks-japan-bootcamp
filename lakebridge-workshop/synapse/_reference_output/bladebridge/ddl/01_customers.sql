-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near ';': missing ')'. SQLSTATE: 42601 (line 12, pos 69)

== SQL ==
EXPLAIN -- Synapse Dedicated SQL Pool: customers table
-- HASH distribution on CustomerID for even distribution across 60 compute nodes

CREATE OR REPLACE TABLE dbo.customers
(
    CustomerID      BIGINT          NOT NULL,
    CustomerName STRING   NOT NULL,
    Email STRING,
    PhoneNumber STRING,
    BirthDate       DATE            ,
    Gender          STRING,
    RegisteredAt    timestamp    NOT NULL DEFAULT current_timestamp();,
---------------------------------------------------------------------^^^
    LastUpdatedAt   timestamp    NOT NULL DEFAULT current_timestamp();,
    IsActive        BOOLEAN             NOT NULL DEFAULT 1
)
;

*/

 ---------------Exception End --------------------
