CREATE
    /* DISTRIBUTION = REPLICATE HEAP */
    -- FIXME: ^^^ The above create table options are unsupported
    TABLE dbo.stores
    (
        StoreID INT NOT NULL,
        StoreName VARCHAR(200) NOT NULL,
        RegionCode VARCHAR(10) NOT NULL,
        PrefectureCode VARCHAR(2) NOT NULL,
        OpenedAt DATE NOT NULL,
        ClosedAt DATE
    );

