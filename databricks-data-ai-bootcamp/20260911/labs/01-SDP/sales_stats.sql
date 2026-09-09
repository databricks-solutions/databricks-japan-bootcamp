CREATE OR REFRESH MATERIALIZED VIEW sales_stats (
    -- 1. LOG（既定）: 平均取引額が妥当な範囲に収まること。
    --    違反はイベントログに記録されるが、行は書き込まれる。
    CONSTRAINT reasonable_avg_value
        EXPECT (avg_txn_value BETWEEN 1 AND 1000),

    -- 2. DROP ROW: 総売上は非負でなければならない。
    --    違反行はターゲットから除外されるが、パイプラインは継続する。
    CONSTRAINT nonneg_revenue
        EXPECT (gross_revenue >= 0) ON VIOLATION DROP ROW,

    -- 3. FAIL UPDATE: product が設定されていなければならない。
    --    違反があると、制約名とともにパイプライン更新全体が中断される。
    CONSTRAINT known_product
        EXPECT (product IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Sales KPIs grouped by product, with data-quality expectations'
AS SELECT
    product,
    COUNT(*)                     AS txn_count,
    SUM(quantity)                AS units_sold,
    ROUND(SUM(totalPrice), 2)    AS gross_revenue,
    ROUND(AVG(totalPrice), 2)    AS avg_txn_value,
    COUNT(DISTINCT customerID)   AS unique_customers,
    COUNT(DISTINCT franchiseID)  AS franchises_selling
FROM sales_transactions
GROUP BY product;
