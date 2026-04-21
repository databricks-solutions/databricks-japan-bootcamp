-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near 'CREATE': extra input 'CREATE'. SQLSTATE: 42601 (line 19, pos 0)

== SQL ==
EXPLAIN CREATE
    /* DISTRIBUTION = HASH (CustomerID) CLUSTERED COLUMNSTORE INDEX */
    -- FIXME: ^^^ The above create table options are unsupported
    TABLE dbo.customers
    (
        CustomerID BIGINT NOT NULL,
        CustomerName VARCHAR(200) NOT NULL,
        Email VARCHAR(255),
        PhoneNumber VARCHAR(20),
        BirthDate DATE,
        Gender CHAR(1),
        RegisteredAt TIMESTAMP NOT NULL DEFAULT SYSUTCDATETIME(),
        LastUpdatedAt TIMESTAMP NOT NULL DEFAULT SYSUTCDATETIME(),
        IsActive BOOLEAN NOT NULL DEFAULT 1
    );



CREATE /* STATISTICS stats_customers_RegisteredAt ON dbo.customers (RegisteredAt) */;
^^^
-- FIXME: TSQL: Databricks SQL has no equivalent to the CREATE STATISTICS command, and it cannot be translated

*/

 ---------------Exception End --------------------
