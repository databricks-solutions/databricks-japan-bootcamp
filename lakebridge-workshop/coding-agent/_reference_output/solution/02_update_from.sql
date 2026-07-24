-- Teradata: ステージング表の値で商品価格を更新する
MERGE INTO products AS product
USING product_price_updates AS update_source
ON product.product_id = update_source.product_id
WHEN MATCHED THEN UPDATE SET
  price = update_source.new_price;
