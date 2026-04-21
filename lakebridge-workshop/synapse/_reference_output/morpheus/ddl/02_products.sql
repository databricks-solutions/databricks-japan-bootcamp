CREATE
    /* DISTRIBUTION = REPLICATE CLUSTERED INDEX (ProductID) */
    -- FIXME: ^^^ The above create table options are unsupported
    TABLE dbo.products
    (
        ProductID INT NOT NULL,
        ProductName VARCHAR(300) NOT NULL,
        CategoryCode VARCHAR(20) NOT NULL,
        UnitPrice DECIMAL(19, 4) NOT NULL,
        Barcode VARCHAR(13),
        LaunchedAt DATE,
        DiscontinuedAt DATE
    );

