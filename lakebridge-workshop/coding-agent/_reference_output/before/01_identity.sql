-- Teradata: IDENTITY 列を持つ注文明細テーブル
CREATE TABLE order_items
(
    order_item_id BIGINT GENERATED ALWAYS AS IDENTITY
        (START WITH 1 INCREMENT BY 1 NO CYCLE) NOT NULL,
    order_id BIGINT NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(19,4) NOT NULL
)

TBLPROPERTIES('delta.feature.allowColumnDefaults' = 'supported');
