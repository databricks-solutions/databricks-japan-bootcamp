-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Reconcile Lab - Setup
-- MAGIC
-- MAGIC Source / Target テーブルを Databricks 内に用意し、意図的に 5 行分の差分を仕込みます。
-- MAGIC
-- MAGIC **実行手順:**
-- MAGIC 1. 下のセルでウィジェットを定義し、画面上部に出てくる `catalog` / `source_schema` / `target_schema` を自分の環境に合わせて設定
-- MAGIC 2. 全セルを順に実行 (`Run All`)

-- COMMAND ----------

-- DBTITLE 1,ウィジェット定義
CREATE WIDGET TEXT catalog DEFAULT "main";
CREATE WIDGET TEXT source_schema DEFAULT "reconcile_source";
CREATE WIDGET TEXT target_schema DEFAULT "reconcile_target";

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 1. Catalog / Schema 作成

-- COMMAND ----------

CREATE CATALOG IF NOT EXISTS IDENTIFIER(:catalog);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER(:catalog || '.' || :source_schema);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER(:catalog || '.' || :target_schema);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 2. Source テーブル: 完全版 (10 行)

-- COMMAND ----------

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:source_schema);

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_date    DATE,
    order_status  STRING,
    total_amount  DECIMAL(18, 2)
);

INSERT INTO orders VALUES
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

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3. Target テーブル: 5 行分の差分を仕込む
-- MAGIC
-- MAGIC - **行欠落**: `1009`, `1010`
-- MAGIC - **値差異**: `1003` の `total_amount` / `1004` の `order_status`
-- MAGIC - **余計な行**: `9001`

-- COMMAND ----------

USE SCHEMA IDENTIFIER(:target_schema);

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_date    DATE,
    order_status  STRING,
    total_amount  DECIMAL(18, 2)
);

INSERT INTO orders VALUES
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

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 4. 確認 (source = 10 行、target = 9 行になっていれば OK)

-- COMMAND ----------

SELECT 'source' AS side, COUNT(*) AS row_count FROM IDENTIFIER(:catalog || '.' || :source_schema || '.orders')
UNION ALL
SELECT 'target' AS side, COUNT(*) AS row_count FROM IDENTIFIER(:catalog || '.' || :target_schema || '.orders');
