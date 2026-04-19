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
