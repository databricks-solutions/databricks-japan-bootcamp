-- Synapse Dedicated SQL Pool: stores table
CREATE TABLE dbo.stores
(
    StoreID         INT             NOT NULL,
    StoreName       NVARCHAR(200)   NOT NULL,
    RegionCode      VARCHAR(10)     NOT NULL,
    PrefectureCode  VARCHAR(2)      NOT NULL,
    OpenedAt        DATE            NOT NULL,
    ClosedAt        DATE            NULL
)
WITH
(
    DISTRIBUTION = REPLICATE,
    HEAP
);
GO
