-- Synapse Dedicated SQL Pool: products table
-- Small master table; replicate across all distributions
CREATE TABLE dbo.products
(
    ProductID       INT             NOT NULL,
    ProductName     NVARCHAR(300)   NOT NULL,
    CategoryCode    VARCHAR(20)     NOT NULL,
    UnitPrice       MONEY           NOT NULL,
    Barcode         VARCHAR(13)     NULL,
    LaunchedAt      DATE            NULL,
    DiscontinuedAt  DATE            NULL
)
WITH
(
    DISTRIBUTION = REPLICATE,
    CLUSTERED INDEX (ProductID)
);
GO
