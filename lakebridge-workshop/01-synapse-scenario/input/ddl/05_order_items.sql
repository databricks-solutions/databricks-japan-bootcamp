-- Synapse Dedicated SQL Pool: order_items table
-- Hash on OrderID to co-locate with orders during joins
CREATE TABLE dbo.order_items
(
    OrderID         BIGINT          NOT NULL,
    LineNumber      INT             NOT NULL,
    ProductID       INT             NOT NULL,
    Quantity        INT             NOT NULL,
    UnitPrice       DECIMAL(18,2)   NOT NULL,
    DiscountAmount  DECIMAL(18,2)   NOT NULL DEFAULT 0,
    LineAmount      AS (Quantity * UnitPrice - DiscountAmount) PERSISTED
)
WITH
(
    DISTRIBUTION = HASH (OrderID),
    CLUSTERED COLUMNSTORE INDEX
);
GO

CREATE STATISTICS stats_order_items_ProductID ON dbo.order_items (ProductID);
GO
