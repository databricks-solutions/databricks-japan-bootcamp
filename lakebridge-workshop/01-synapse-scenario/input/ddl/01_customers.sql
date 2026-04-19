-- Synapse Dedicated SQL Pool: customers table
-- HASH distribution on CustomerID for even distribution across 60 compute nodes
CREATE TABLE dbo.customers
(
    CustomerID      BIGINT          NOT NULL,
    CustomerName    NVARCHAR(200)   NOT NULL,
    Email           NVARCHAR(255)   NULL,
    PhoneNumber     VARCHAR(20)     NULL,
    BirthDate       DATE            NULL,
    Gender          CHAR(1)         NULL,
    RegisteredAt    DATETIME2(3)    NOT NULL DEFAULT SYSUTCDATETIME(),
    LastUpdatedAt   DATETIME2(3)    NOT NULL DEFAULT SYSUTCDATETIME(),
    IsActive        BIT             NOT NULL DEFAULT 1
)
WITH
(
    DISTRIBUTION = HASH (CustomerID),
    CLUSTERED COLUMNSTORE INDEX
);
GO

CREATE STATISTICS stats_customers_RegisteredAt ON dbo.customers (RegisteredAt);
GO
