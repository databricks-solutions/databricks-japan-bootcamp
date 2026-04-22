-------------- Exception Start-------------------
/*

[PARSE_SYNTAX_ERROR] Syntax error at or near ';': extra input ';'. SQLSTATE: 42601 (line 11, pos 51)

== SQL ==
EXPLAIN -- ==========================================
-- T-SQL EXAMPLE #1: Multi-Statement Data Transformation
-- ==========================================

-- Create a table for product data

CREATE OR REPLACE TABLE Products (
    ProductID INT,
    ProductName STRING,
    Price DECIMAL(19,4),
    CreatedAt TIMESTAMP DEFAULT current_timestamp(););
---------------------------------------------------^^^
-- Insert some sample products

INSERT INTO Products 
(ProductID, ProductName, Price)
VALUES
    (101, 'Widget A', 12.50),
    (102, 'Widget B', 19.99),
    (103, 'Widget C', 29.75);
-- Create a temporary table to capture discounted items

CREATE TEMPORARY TABLE TEMP_TABLE_Discounts (
    ProductID INT,
    DiscountRate DOUBLE
);
-- Insert discount rates

INSERT INTO TEMP_TABLE_Discounts 
(ProductID, DiscountRate)
VALUES
    (101, 0.10),
    (103, 0.25);
-- Update product prices where a discount is applicable
-- (T-SQL allows an UPDATE with a FROM clause)

MERGE INTO Products p_TGT
USING (
SELECT * 
FROM Products p
INNER JOIN TEMP_TABLE_Discounts d ON p.ProductID = d.ProductID
)
ON 
COALESCE(p.Price::string,'__NULL__') = COALESCE(p_TGT.Price::string,'__NULL__') AND 
COALESCE(p.ProductID::string,'__NULL__') = COALESCE(p_TGT.ProductID::string,'__NULL__')
WHEN MATCHED THEN UPDATE SET
Price = p.Price * ( 1 - d.DiscountRate );
-- Demonstrate a conditional DELETE
-- Suppose we delete any product older than 7 days with no discounts
-- (Pretend we have some reason to prune old, non-discounted items)

DELETE p
FROM Products p
WHERE p.CreatedAt < DATEADD(DAY, -7, current_timestamp())
  AND p.ProductID NOT IN (SELECT ProductID FROM TEMP_TABLE_Discounts);
-- Final SELECT to confirm changes

SELECT * FROM Products;
-- Clean up permanent table only
-- DROP TABLE IF EXISTS #Discounts; -- Temp tables are automatically dropped at the end of the session

DROP TABLE IF EXISTS Products;

*/

 ---------------Exception End --------------------
