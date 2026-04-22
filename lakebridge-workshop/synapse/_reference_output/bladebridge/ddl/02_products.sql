-- Synapse Dedicated SQL Pool: products table
-- Small master table; replicate across all distributions

CREATE OR REPLACE TABLE dbo.products
(
    ProductID       INT             NOT NULL,
    ProductName STRING   NOT NULL,
    CategoryCode STRING     NOT NULL,
    UnitPrice       DECIMAL(19,4)           NOT NULL,
    Barcode STRING,
    LaunchedAt      DATE            ,
    DiscontinuedAt  DATE            
)
;
