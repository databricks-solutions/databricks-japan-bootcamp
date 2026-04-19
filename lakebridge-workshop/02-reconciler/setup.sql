-- =====================================================
-- Lab 2: Reconciler セットアップ SQL
-- Source / Target を Databricks 内に用意し、意図的に 5 行の差分を仕込む
-- =====================================================

-- ユーザーごとにぶつからないよう、自分のユーザー名等を入れた catalog/schema を事前に使う想定。
-- 参加者は <catalog>, <schema> を自分の環境に合わせて置換してから実行。
-- 例: main.<your_name>_recon_src / main.<your_name>_recon_tgt

-- ---------------------------------------------------
-- 1. Source 側カタログ/スキーマ作成
-- ---------------------------------------------------
CREATE CATALOG IF NOT EXISTS main;
CREATE SCHEMA IF NOT EXISTS main.recon_src;
CREATE SCHEMA IF NOT EXISTS main.recon_tgt;

-- ---------------------------------------------------
-- 2. Source テーブル: 完全版
-- ---------------------------------------------------
DROP TABLE IF EXISTS main.recon_src.orders;
CREATE TABLE main.recon_src.orders (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_date    DATE,
    order_status  STRING,
    total_amount  DECIMAL(18, 2)
);

INSERT INTO main.recon_src.orders VALUES
    (1001, 501, DATE '2026-03-01', 'PLACED',    1200.00),
    (1002, 502, DATE '2026-03-02', 'PLACED',     750.50),
    (1003, 503, DATE '2026-03-03', 'SHIPPED',   3200.00),
    (1004, 501, DATE '2026-03-04', 'DELIVERED', 4500.00),
    (1005, 504, DATE '2026-03-05', 'PLACED',     900.00),
    (1006, 505, DATE '2026-03-06', 'CANCELLED',  180.00),
    (1007, 502, DATE '2026-03-07', 'DELIVERED', 2100.00),
    (1008, 506, DATE '2026-03-08', 'SHIPPED',   5400.00),
    (1009, 507, DATE '2026-03-09', 'PLACED',    1350.00),
    (1010, 508, DATE '2026-03-10', 'DELIVERED',  650.00);

-- ---------------------------------------------------
-- 3. Target テーブル: 5 行分の差分を仕込む
--    (a) 行欠落: 1009, 1010
--    (b) 値差異: 1003 の amount, 1004 の status
--    (c) 余計な行: 9001
-- ---------------------------------------------------
DROP TABLE IF EXISTS main.recon_tgt.orders;
CREATE TABLE main.recon_tgt.orders (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_date    DATE,
    order_status  STRING,
    total_amount  DECIMAL(18, 2)
);

INSERT INTO main.recon_tgt.orders VALUES
    (1001, 501, DATE '2026-03-01', 'PLACED',    1200.00),
    (1002, 502, DATE '2026-03-02', 'PLACED',     750.50),
    (1003, 503, DATE '2026-03-03', 'SHIPPED',   3250.00),    -- amount 差異
    (1004, 501, DATE '2026-03-04', 'SHIPPED',   4500.00),    -- status 差異
    (1005, 504, DATE '2026-03-05', 'PLACED',     900.00),
    (1006, 505, DATE '2026-03-06', 'CANCELLED',  180.00),
    (1007, 502, DATE '2026-03-07', 'DELIVERED', 2100.00),
    (1008, 506, DATE '2026-03-08', 'SHIPPED',   5400.00),
    -- 1009, 1010 は意図的に欠落
    (9001, 999, DATE '2026-03-11', 'PLACED',     100.00);    -- 余計な行

-- ---------------------------------------------------
-- 4. 確認
-- ---------------------------------------------------
SELECT COUNT(*) AS src_count FROM main.recon_src.orders;  -- 10
SELECT COUNT(*) AS tgt_count FROM main.recon_tgt.orders;  --  9
