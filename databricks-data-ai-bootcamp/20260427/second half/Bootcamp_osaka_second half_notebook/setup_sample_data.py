# Databricks notebook source
# MAGIC %md
# MAGIC # Bootcamp大阪 サンプルデータ作成
# MAGIC
# MAGIC このノートブックは **AIデータ加工ハンズオンが始まる前に実行してください**。
# MAGIC ご自身の Databricks Free Edition 環境にサンプルデータ（5テーブル）が作成されます。
# MAGIC
# MAGIC ## ⚠️ 事前設定: コンピュートの選択
# MAGIC
# MAGIC **ノートブック右上の接続先を「サーバーレス」に変更してください**。
# MAGIC
# MAGIC - ❌ `Serverless Starter Warehouse`（SQLウェアハウス）→ Python が動かない
# MAGIC - ✅ `サーバーレス`（ノートブック用コンピュート）→ Python も SQL も動く
# MAGIC
# MAGIC SQLウェアハウスのままだと `Unsupported cell during execution. SQL warehouses only support executing SQL cells.` というエラーが出ます。
# MAGIC
# MAGIC ## 実行方法
# MAGIC
# MAGIC 1. 上記のとおり、接続先を **「サーバーレス」** に変更
# MAGIC 2. 上部の **「すべてを実行」** をクリック
# MAGIC 3. 実行完了まで約2〜3分
# MAGIC 4. `workspace.bootcamp_osaka` スキーマに5つのテーブルが作成されます
# MAGIC
# MAGIC ## 作成するデータ
# MAGIC
# MAGIC **架空のECサイト「Brick EC」のデータ**
# MAGIC
# MAGIC | テーブル | 行数 | 用途 |
# MAGIC |---|---|---|
# MAGIC | `gold_users` | 500 | ユーザー属性 |
# MAGIC | `gold_products` | 38 | 商品カタログ |
# MAGIC | `gold_transactions` | 3,000 | 購買履歴 |
# MAGIC | `gold_reviews` | 1,000 | **レビュー本文（AIデータ加工ハンズオンで使用）** |
# MAGIC | `support_inquiries` | 300 | **問い合わせ内容（AIデータ加工ハンズオンの発展問題で使用）** |
# MAGIC
# MAGIC ## セッションでの使われ方
# MAGIC
# MAGIC - **AIデータ加工ハンズオン**: gold_reviews / support_inquiries に ai_classify/ai_query を適用

# COMMAND ----------

catalog_name = "workspace"
schema_name = "bootcamp_osaka"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_name}.{schema_name}")
spark.sql(f"USE CATALOG {catalog_name}")
spark.sql(f"USE SCHEMA {schema_name}")
print(f"スキーマ準備完了: {catalog_name}.{schema_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. gold_users（ユーザー属性）

# COMMAND ----------

import random
from datetime import datetime, timedelta

random.seed(42)

regions = ['東京', '大阪', '愛知', '福岡', '北海道', '神奈川', '埼玉', '千葉', '兵庫', '京都']
age_groups = ['20代', '30代', '40代', '50代', '60代以上']
genders = ['男性', '女性', 'その他']

users_data = []
for uid in range(1, 501):
    users_data.append((
        f"USER{uid:04d}",
        f"user{uid}@example.com",
        random.choice(age_groups),
        random.choice(genders),
        random.choice(regions),
        (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))).strftime('%Y-%m-%d'),
        random.choice(['ブロンズ', 'シルバー', 'ゴールド', 'プラチナ']),
    ))

users_df = spark.createDataFrame(
    users_data,
    ["user_id", "email", "age_group", "gender", "region", "registered_date", "membership_tier"]
)
users_df.write.mode("overwrite").saveAsTable("gold_users")

spark.sql("""
    ALTER TABLE gold_users SET TBLPROPERTIES (
      'comment' = 'Brick ECのユーザーマスタ。会員登録情報と属性。'
    )
""")
spark.sql("ALTER TABLE gold_users ALTER COLUMN user_id COMMENT 'ユーザーID（一意）'")
spark.sql("ALTER TABLE gold_users ALTER COLUMN age_group COMMENT '年齢層（20代/30代/40代/50代/60代以上）'")
spark.sql("ALTER TABLE gold_users ALTER COLUMN region COMMENT '居住地域（都道府県レベル）'")
spark.sql("ALTER TABLE gold_users ALTER COLUMN membership_tier COMMENT '会員ランク（ブロンズ〜プラチナ）'")

print(f"gold_users: {users_df.count()}行")
display(users_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. gold_products（商品カタログ）

# COMMAND ----------

categories = {
    '食品': ['お米', 'パスタ', 'オリーブオイル', 'コーヒー豆', '紅茶', 'チョコレート', '日本酒', 'ワイン'],
    '日用品': ['シャンプー', 'ボディソープ', '歯磨き粉', '洗剤', 'トイレットペーパー'],
    '家電': ['電子レンジ', '炊飯器', 'コーヒーメーカー', '空気清浄機', 'ドライヤー'],
    'ファッション': ['Tシャツ', 'ジーンズ', 'スニーカー', 'バッグ', '時計'],
    '書籍': ['小説', 'ビジネス書', '技術書', 'マンガ', '雑誌'],
    'スポーツ': ['ヨガマット', 'ダンベル', 'ランニングシューズ', 'テニスラケット', 'ゴルフボール'],
    '美容': ['化粧水', '乳液', '口紅', 'ファンデーション', '香水'],
}

products_data = []
pid = 1
for cat, names in categories.items():
    for name in names:
        products_data.append((
            f"PROD{pid:04d}",
            f"{name}（Brick EC限定）",
            cat,
            round(random.uniform(500, 50000)),
            random.choice(['在庫あり', '残りわずか', '取り寄せ']),
        ))
        pid += 1

products_df = spark.createDataFrame(
    products_data,
    ["product_id", "product_name", "category", "price", "stock_status"]
)
products_df.write.mode("overwrite").saveAsTable("gold_products")

spark.sql("""ALTER TABLE gold_products SET TBLPROPERTIES (
    'comment' = 'Brick EC商品マスタ。カテゴリー別の商品情報。')""")
spark.sql("ALTER TABLE gold_products ALTER COLUMN category COMMENT '商品カテゴリー（食品/日用品/家電/ファッション/書籍/スポーツ/美容）'")
spark.sql("ALTER TABLE gold_products ALTER COLUMN price COMMENT '販売価格（円）'")

print(f"gold_products: {products_df.count()}行")
display(products_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. gold_transactions（購買履歴）

# COMMAND ----------

user_ids = [row.user_id for row in spark.table("gold_users").collect()]
product_rows = spark.table("gold_products").collect()

transactions_data = []
for tid in range(1, 3001):
    user = random.choice(user_ids)
    product = random.choice(product_rows)
    qty = random.randint(1, 5)
    transactions_data.append((
        f"TXN{tid:06d}",
        user,
        product.product_id,
        qty,
        product.price * qty,
        (datetime(2025, 1, 1) + timedelta(days=random.randint(0, 480))).strftime('%Y-%m-%d'),
        random.choice(['クレジットカード', 'PayPay', 'コンビニ決済', '代引き']),
    ))

transactions_df = spark.createDataFrame(
    transactions_data,
    ["transaction_id", "user_id", "product_id", "quantity", "amount", "transaction_date", "payment_method"]
)
transactions_df.write.mode("overwrite").saveAsTable("gold_transactions")

spark.sql("""ALTER TABLE gold_transactions SET TBLPROPERTIES (
    'comment' = 'Brick ECの購買履歴。ユーザーごとの注文記録。')""")
spark.sql("ALTER TABLE gold_transactions ALTER COLUMN amount COMMENT '購入金額合計（円）= price × quantity'")

print(f"gold_transactions: {transactions_df.count()}行")
display(transactions_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. gold_reviews（レビュー本文）★ai_query用
# MAGIC
# MAGIC **このテーブルが後半⑤のAIデータ加工で主役になります。**
# MAGIC 自由文のレビュー本文に対して ai_classify や ai_query を適用します。

# COMMAND ----------

# リアルなレビュー文のサンプル（60パターン: ポジティブ・ネガティブ・ニュートラル・改善提案・問題報告を混在）
review_templates = [
    # ポジティブ（大満足）
    ("商品の品質が期待以上で大満足です。配送も迅速でした。また利用します。", 5),
    ("想像していた通りの商品で、使い心地も抜群でした。リピート確定です。", 5),
    ("デザインが気に入りました。注文から到着まで早くて助かりました。", 5),
    ("梱包も丁寧で、商品に傷もなく、非常に満足しています。", 5),
    ("友人へのプレゼントに購入しましたが、とても喜んでもらえました。", 5),
    ("期待以上の素晴らしい商品でした。また購入したいと思います。", 5),
    ("家族全員が気に入り、追加でもう1つ買いました。", 5),
    ("写真よりも実物の方が綺麗で、買って正解でした。", 5),
    ("丁寧な対応とスピーディーな発送に感動しました。", 5),
    ("リピーターです。いつも品質が安定していて信頼できます。", 5),
    # ポジティブ（満足）
    ("値段の割にクオリティが高く、コスパが素晴らしい。友人にもお勧めしました。", 4),
    ("思っていたより良い商品でした。次も買いたいです。", 4),
    ("日常使いに十分な品質。価格も手頃で満足です。", 4),
    ("デザインは気に入っていますが、少し重めなのが残念。", 4),
    ("全体的には満足。あと少し改良があれば完璧です。", 4),
    ("良い買い物でした。配送の速さも素晴らしい。", 4),
    ("予想以上に良かったですが、期待していた機能が一部足りず星4つに。", 4),
    ("商品自体は良いので、あとは価格がもう少し安ければ。", 4),
    # ニュートラル
    ("普通の商品でした。特に良くも悪くもないです。", 3),
    ("値段相応の商品だと思います。可もなく不可もなく。", 3),
    ("使用期間が短いのでまだ評価できません。", 3),
    ("まあまあです。他の商品と比べて特筆する点はありません。", 3),
    ("配送が予定より遅れて届きました。次回は改善をお願いします。", 3),
    ("説明書が分かりにくかったので、動画マニュアルがあると助かります。", 3),
    ("思ったのと少し違いましたが、使えないことはないです。", 3),
    ("可もなく不可もなく、無難な選択だったと思います。", 3),
    # 改善提案型
    ("商品は良いのですが、パッケージがもう少し環境に優しいと嬉しいです。", 4),
    ("サイズ展開がもっとあればもっと買いたい。", 4),
    ("色のバリエーションを増やしてほしいです。", 4),
    ("もう少し大きいサイズがあると家族でシェアできるので嬉しいです。", 4),
    ("充電ケーブルも付属してくれると親切だと思います。", 4),
    ("ギフトラッピングのオプションがあると嬉しいです。", 4),
    ("アプリ連携機能があればもっと便利になりそう。", 3),
    ("説明動画がYouTubeにあると助かります。", 3),
    ("箱が大きすぎるので、もっとコンパクトな梱包を希望します。", 3),
    ("定期便のサブスク割引があれば継続しやすいです。", 4),
    # ネガティブ（軽度）
    ("商品が届いた時点で箱が潰れていました。中身は無事でしたが残念です。", 2),
    ("サイズが想像より小さく、返品を検討中です。説明をもっと詳しくしてほしい。", 2),
    ("思っていた色と違いました。画像と実物の差が大きすぎます。", 2),
    ("味が期待外れでした。他のブランドの方が美味しかったです。", 2),
    ("期待していた機能が使えず、残念でした。", 2),
    ("匂いが強くて気になりました。もう少し抑えてほしい。", 2),
    ("組み立てが思ったより大変で、一人では難しかったです。", 2),
    ("思ったほど効果を感じられませんでした。", 2),
    ("使いづらく、すぐに使わなくなってしまいました。", 2),
    ("商品画像と実物の印象がかなり違います。", 2),
    # ネガティブ（重度・問題報告）
    ("初期不良がありました。交換対応は迅速でしたが、品質管理の改善をお願いします。", 2),
    ("使用して1週間で壊れました。耐久性に問題があると思います。", 1),
    ("注文したものと違う商品が届きました。確認をしっかりお願いします。", 1),
    ("2回目の使用で故障。品質に疑問を感じます。", 1),
    ("届いた商品が破損していました。すぐに返品手続きをしました。", 1),
    ("カスタマーサポートの対応が遅く、不満です。", 1),
    ("返品処理に2週間以上かかり、その間連絡もなくストレスでした。", 1),
    ("商品の説明と異なる内容で、非常に残念です。", 1),
    ("購入後すぐに同じ商品がセールになっていて損した気分です。", 2),
    ("配送時に箱が開封された形跡がありました。セキュリティを強化してほしい。", 1),
    # ポジティブ（サービス評価）
    ("カスタマーサポートの対応が丁寧で助かりました。", 5),
    ("問い合わせへの返信が迅速で、安心して購入できました。", 5),
    ("定期的にクーポンが届くので、継続的に利用しています。", 4),
    ("会員ランクが上がると特典が増えて嬉しいです。", 4),
    ("サイトが使いやすく、検索も簡単で買い物がスムーズ。", 4),
]

# 60パターンから1000行生成（平均16-17回ずつ使用）
TARGET_REVIEWS = 1000
reviews_data = []
tx_rows = spark.table("gold_transactions").limit(TARGET_REVIEWS).collect()
for i, tx in enumerate(tx_rows):
    template, rating = random.choice(review_templates)
    reviews_data.append((
        f"REV{i+1:05d}",
        tx.transaction_id,
        tx.user_id,
        tx.product_id,
        rating,
        template,
        (datetime.strptime(tx.transaction_date, '%Y-%m-%d') + timedelta(days=random.randint(1, 14))).strftime('%Y-%m-%d'),
    ))

reviews_df = spark.createDataFrame(
    reviews_data,
    ["review_id", "transaction_id", "user_id", "product_id", "rating", "review_text", "review_date"]
)
reviews_df.write.mode("overwrite").saveAsTable("gold_reviews")

spark.sql("""ALTER TABLE gold_reviews SET TBLPROPERTIES (
    'comment' = 'Brick ECの商品レビュー。ai_query/ai_classifyで活用する自由文テキストを含む。')""")
spark.sql("ALTER TABLE gold_reviews ALTER COLUMN rating COMMENT '評価（1〜5）'")
spark.sql("ALTER TABLE gold_reviews ALTER COLUMN review_text COMMENT '自由記述のレビュー本文'")

print(f"gold_reviews: {reviews_df.count()}行")
display(reviews_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. support_inquiries（問い合わせ内容）★ai_classify用

# COMMAND ----------

inquiry_templates = [
    # 配送関連
    "注文した商品がまだ届きません。発送状況を確認してほしい。",
    "配送日時の指定を変更できますか？",
    "配送先住所を変更したいです。",
    "不在時の荷物の再配達を依頼したいです。",
    "海外発送は対応していますか？",
    "配送業者を指定することはできますか？",
    # 返品・交換関連
    "返品をしたいのですが、手続き方法を教えてください。",
    "商品に不良がありました。交換をお願いします。",
    "サイズ交換は可能ですか？",
    "開封済みの商品でも返品できますか？",
    "使用後の返品は受け付けていますか？",
    "返送料はどちらが負担しますか？",
    "返金までにどのくらい時間がかかりますか？",
    # 支払い関連
    "クーポンコードが使えませんでした。なぜですか。",
    "支払い方法を後から変更できますか？",
    "領収書の発行をお願いします。",
    "分割払いは可能ですか？",
    "コンビニ決済の支払期限が過ぎてしまいました。",
    "決済エラーが出て注文できません。原因を教えてください。",
    "PayPay残高で支払いたいのですが、設定方法は？",
    # アカウント関連
    "パスワードを忘れてしまいました。リセット方法は？",
    "会員ランクはどうすれば上がりますか？",
    "アカウントを削除したいです。手順を教えてください。",
    "メールアドレスを変更したいです。",
    "2段階認証を設定したいです。",
    "ログインできなくなってしまいました。",
    # ポイント・特典関連
    "ポイントの有効期限を確認したいです。",
    "誕生日クーポンが届いていません。",
    "招待プログラムの特典はいつ反映されますか？",
    "ポイント付与が反映されていません。",
    # 商品・使い方関連
    "お気に入りリストに追加した商品が消えてしまいました。",
    "商品の使い方が分からないので教えてほしい。",
    "カートに入れた商品の一部が勝手に削除されました。",
    "商品在庫はいつ頃復活しますか？",
    "商品の仕様について詳しく知りたいです。",
    "取扱説明書を紛失したので再送してほしい。",
    # その他
    "退会理由のアンケートに答えたいです。",
    "御社のSNSアカウントを教えてください。",
    "法人向けの請求書払いに対応していますか？",
    "プレゼント用のラッピング対応は可能ですか？",
    "商品を大量購入したい場合、割引はありますか？",
]

inquiry_data = []
for i in range(300):
    inquiry_data.append((
        f"INQ{i+1:04d}",
        random.choice(user_ids),
        random.choice(inquiry_templates),
        random.choice(['未対応', '対応中', '完了']),
        (datetime(2026, 1, 1) + timedelta(days=random.randint(0, 100))).strftime('%Y-%m-%d %H:%M:%S'),
    ))

inquiries_df = spark.createDataFrame(
    inquiry_data,
    ["inquiry_id", "user_id", "inquiry_text", "status", "submitted_at"]
)
inquiries_df.write.mode("overwrite").saveAsTable("support_inquiries")

spark.sql("""ALTER TABLE support_inquiries SET TBLPROPERTIES (
    'comment' = 'カスタマーサポートへの問い合わせ履歴。ai_classifyでカテゴリ自動分類に使える。')""")

print(f"support_inquiries: {inquiries_df.count()}行")
display(inquiries_df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 準備完了
# MAGIC
# MAGIC 以下のテーブルが使えるようになりました：
# MAGIC
# MAGIC ```
# MAGIC workspace.bootcamp_osaka.gold_users          (500行)
# MAGIC workspace.bootcamp_osaka.gold_products       (50行)
# MAGIC workspace.bootcamp_osaka.gold_transactions   (3000行)
# MAGIC workspace.bootcamp_osaka.gold_reviews        (1,000行)  ← ai_query/ai_classify用
# MAGIC workspace.bootcamp_osaka.support_inquiries   (300行)  ← ai_classify用
# MAGIC ```
# MAGIC
# MAGIC ### Genieスペース作成のヒント（前半用）
# MAGIC - カタログ: `workspace`
# MAGIC - スキーマ: `bootcamp_osaka`
# MAGIC - 全テーブルを選択
# MAGIC - Instruction: 「日本語で回答してください」
# MAGIC
# MAGIC ### ダッシュボード作成のヒント（前半用）
# MAGIC - 地域別ユーザー数（gold_users）
# MAGIC - カテゴリ別売上（gold_transactions × gold_products）
# MAGIC - 年齢層別の購買傾向
# MAGIC - 会員ランク別の購買金額

# COMMAND ----------

# 確認クエリ
spark.sql(f"SHOW TABLES IN {catalog_name}.{schema_name}").display()
