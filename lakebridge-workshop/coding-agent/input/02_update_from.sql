-- Teradata: ステージング表の値で商品価格を更新する
UPDATE products product
FROM product_price_updates update_source
SET product.price = update_source.new_price
WHERE product.product_id = update_source.product_id;
