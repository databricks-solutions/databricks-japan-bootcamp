-- Synapse Dedicated SQL Pool: stores table

CREATE OR REPLACE TABLE dbo.stores
(
    StoreID         INT             NOT NULL,
    StoreName STRING   NOT NULL,
    RegionCode STRING     NOT NULL,
    PrefectureCode STRING      NOT NULL,
    OpenedAt        DATE            NOT NULL,
    ClosedAt        DATE            
)
;
