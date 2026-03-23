def get_quantity_price_rules():
  return {
      # 購入数量が1以上でないものは不正な販売履歴とみなす
      "quantity_is_more_than_1": "quantity >= 1",
      # 購入代金が0より大きくないものは不正な販売履歴とみなす
      "transaction_price_is_more_than_0": "transaction_price > 0",
  }

def get_master_check_rules():
  return {
      # 販売履歴に商品マスターを左外部結合した時、products側のPrimary Keyである
      # products_idがNULLである場合(つまり紐付けられなかった場合) は、
      # 商品マスターに存在しない商品の販売履歴となるため、不正データとみなす
      "product_id_is_not_null": "products.product_id IS NOT NULL",
      # 販売履歴に顧客マスターを左外部結合した時、users側のPrimary Keyである
      # user_idがNULLである場合(つまり紐付けられなかった場合) は、
      # 顧客マスターに存在しない加入者の販売履歴となるため、不正データとみなす
      "user_id_is_not_null": "users.user_id IS NOT NULL",
  }