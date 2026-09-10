# Databricks notebook source
# MAGIC %md
# MAGIC # 05. 初期セットアップ（データ生成込み・Free Edition 版）
# MAGIC
# MAGIC このノートブック **単体** で、以下をまとめて実施する（従来の `admin/00` の生成処理を統合）。
# MAGIC 1. 共通変数の定義（カタログ `workspace` / スキーマ `de_workshop` / Volume パス）
# MAGIC 2. スキーマと Volume（`landing` / `master` / `checkpoints`）の作成
# MAGIC 3. **サンプルデータ生成**（マスター 3 表 → `master`、ファクト 4 表 → `landing`）
# MAGIC 4. `master` のマスター Parquet を Bronze マスターテーブル（`bronze_m_*` ＋ PK）として取り込み
# MAGIC
# MAGIC - 生成は **dbldatagen を使わず PySpark のみ**で行うため `%pip` / `restartPython` 不要。
# MAGIC   後続の `10/20/30` から `%run ./05_setup` されても安全（変数が保持される）。
# MAGIC - **冪等**: データが既に生成済みなら生成をスキップする（`%run` のたびに再生成しない）。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 変数定義（Free Edition 固定値）

# COMMAND ----------

from pyspark.sql import functions as F

catalog = "workspace"     # Free Edition の既定カタログ
schema  = "de_workshop"   # 固定スキーマ
bp = f"{catalog}.{schema}"

landing         = f"/Volumes/{catalog}/{schema}/landing"       # ファクト Parquet
master          = f"/Volumes/{catalog}/{schema}/master"        # マスター Parquet
checkpoint_base = f"/Volumes/{catalog}/{schema}/checkpoints"   # Auto Loader チェックポイント

# ★マスターテーブルの再作成制御（True: 常に作り直す / False: 未作成のみ）
replace_master_tables = False

# 生成件数（本番相当。重い場合は縮小可）
num_customers = 5000
num_merchants = 500
num_payment_methods = int(num_customers * 1.8)
num_payments = 100000
num_points   = 20000
num_charges  = 2000
num_logins   = 20000
fraud_rate = 0.10
DATE_START = "2026-01-01 00:00:00"
DATE_END   = "2026-06-30 23:59:59"

print(f"catalog={catalog}, schema={schema}")
print(f"landing={landing}\nmaster={master}\ncheckpoint_base={checkpoint_base}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマと Volume を作成（冪等）

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
for v in ["landing", "master", "checkpoints"]:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{v}")
print(f"作成: スキーマ {bp} / Volume landing・master・checkpoints")

# COMMAND ----------

# MAGIC %md
# MAGIC ## サンプルデータ生成（未生成のときだけ実行）
# MAGIC 架空のキャッシュレス決済サービスを模した不正検知用データを PySpark で生成し、
# MAGIC マスターを `master` Volume、ファクトを `landing` Volume に **Parquet** で出力する。

# COMMAND ----------

def _has_files(path: str) -> bool:
    try:
        return len([f for f in dbutils.fs.ls(path) if not f.name.startswith("_")]) > 0
    except Exception:
        return False

def _pick(id_col, salt, values):
    """id と salt のハッシュで values から 1 つ選ぶ（決定的・ほぼ一様）"""
    arr = F.array(*[F.lit(v) for v in values])
    return F.element_at(arr, (F.abs(F.hash(F.concat(id_col.cast("string"), F.lit(salt)))) % len(values)) + 1)

_already = _has_files(f"{master}/m_customers/") and _has_files(f"{landing}/t_payments/")
if _already:
    print("サンプルデータは生成済み → 生成をスキップ")
else:
    print("サンプルデータを生成します ...")

    PREF = ["東京都","神奈川県","大阪府","愛知県","埼玉県","千葉県","兵庫県","北海道","福岡県","静岡県",
            "京都府","広島県","宮城県","新潟県","長野県","岐阜県","群馬県","栃木県","岡山県","福島県"]
    LAST = ["佐藤","鈴木","高橋","田中","伊藤","渡辺","山本","中村","小林","加藤"]
    FIRST= ["太郎","次郎","健太","翔太","蓮","美咲","結衣","陽菜","美月","優子"]
    PLAN = ["5G無制限プラン","スタンダードプラン","ライト3GB","ライト6GB","ライト9GB","オンライン専用プラン"]
    CSTAT= ["アクティブ","休止","解約"]
    DEV  = ["スマートフォン","PC","タブレット"]
    MCAT = ["コンビニ","スーパー","飲食","ドラッグストア","ECサイト","家電量販","アパレル","交通","エンタメ"]
    MTYPE= ["QR決済","クレジットカード","iD","デビットカード"]

    _ip = F.concat(F.floor(F.rand()*200+1).cast("string"), F.lit("."),
                   F.floor(F.rand()*256).cast("string"), F.lit("."),
                   F.floor(F.rand()*256).cast("string"), F.lit(".***"))

    # --- マスター：会員 ---
    customers = (spark.range(num_customers)
        .withColumn("customer_id", F.format_string("C%09d", F.col("id")))
        .withColumn("last_name",  _pick(F.col("id"), "ln", LAST))
        .withColumn("first_name", _pick(F.col("id"), "fn", FIRST))
        .withColumn("gender", _pick(F.col("id"), "g", ["M","F"]))
        .withColumn("birth_date", F.expr("date_add(date'1960-01-01', cast(rand()*16800 as int))"))
        .withColumn("prefecture", _pick(F.col("id"), "pref", PREF))
        .withColumn("registration_date", F.expr("date_add(date'2019-01-01', cast(rand()*2557 as int))"))
        .withColumn("telecom_plan", _pick(F.col("id"), "plan", PLAN))
        .withColumn("customer_status", _pick(F.col("id"), "st", CSTAT))
        .withColumn("avg_monthly_spend", (F.rand()*75000+5000).cast("int"))
        .withColumn("primary_device_id", F.format_string("DEV%010d", F.col("id")))
        .drop("id"))
    customers.write.mode("overwrite").parquet(f"{master}/m_customers/")

    # --- マスター：加盟店 ---
    merchants = (spark.range(num_merchants)
        .withColumn("merchant_id", F.format_string("M%06d", F.col("id")))
        .withColumn("category", _pick(F.col("id"), "cat", MCAT))
        .withColumn("prefecture", _pick(F.col("id"), "mpref", PREF))
        .withColumn("merchant_name", F.concat(_pick(F.col("id"),"cat",MCAT), F.lit("店"),
                    (F.abs(F.hash("merchant_id")) % 300 + 1).cast("string"), F.lit("号")))
        .drop("id"))
    merchants.write.mode("overwrite").parquet(f"{master}/m_merchants/")

    # --- マスター：決済手段 ---
    pmethods = (spark.range(num_payment_methods)
        .withColumn("method_id", F.format_string("PM%08d", F.col("id")))
        .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
        .withColumn("method_type", _pick(F.col("id"), "mt", MTYPE))
        .withColumn("card_number_masked", F.concat(F.lit("****-****-****-"), F.format_string("%04d", F.floor(F.rand()*10000).cast("int"))))
        .withColumn("registered_date", F.expr("date_add(date'2019-01-01', cast(rand()*2557 as int))"))
        .withColumn("status", _pick(F.col("id"), "pmst", ["有効","停止","期限切れ"]))
        .drop("id"))
    pmethods.write.mode("overwrite").parquet(f"{master}/m_payment_methods/")

    # --- ファクト：決済（不正パターン注入） ---
    base = F.unix_timestamp(F.lit(DATE_START))
    span = F.unix_timestamp(F.lit(DATE_END)) - F.unix_timestamp(F.lit(DATE_START))
    pay = (spark.range(num_payments)
        .withColumn("payment_id", F.format_string("PAY%012d", F.col("id")))
        .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
        .withColumn("merchant_id", F.format_string("M%06d", F.floor(F.rand()*num_merchants).cast("long")))
        .withColumn("method_id", F.format_string("PM%08d", F.floor(F.rand()*num_payment_methods).cast("long")))
        .withColumn("payment_timestamp", F.to_timestamp(F.from_unixtime(base + (F.rand()*span).cast("long"))))
        .withColumn("amount", (F.rand()*49900+100).cast("int"))
        .withColumn("status", _pick(F.col("id"), "pst", ["完了","完了","完了","完了","キャンセル","返金","エラー"]))
        .withColumn("device_type", _pick(F.col("id"), "dt", DEV))
        .withColumn("device_id", F.format_string("DEV%010d", F.floor(F.rand()*num_customers*2).cast("long")))
        .withColumn("transaction_prefecture", _pick(F.col("id"), "tp", PREF))
        .withColumn("ip_address_masked", _ip)
        .drop("id"))
    pay = pay.withColumn("is_fraud", F.rand() < fraud_rate)
    pay = pay.withColumn("_pat",
        F.when(~F.col("is_fraud"), F.lit("normal"))
         .when(F.rand()<0.30, F.lit("深夜大量"))
         .when(F.rand()<0.36, F.lit("地理異常"))
         .when(F.rand()<0.44, F.lit("高額異常"))
         .when(F.rand()<0.60, F.lit("カードテスト"))
         .otherwise(F.lit("乗っ取り")))
    pay = pay.join(customers.select("customer_id",
                    F.col("prefecture").alias("home_pref"), "avg_monthly_spend", "primary_device_id"),
                   on="customer_id", how="left")
    # 深夜大量: 2〜5時台
    pay = pay.withColumn("payment_timestamp",
        F.when(F.col("_pat")=="深夜大量",
               F.expr("date_trunc('day', payment_timestamp) + make_interval(0,0,0,0,cast(floor(rand()*3+2) as int),cast(floor(rand()*60) as int),0)"))
         .otherwise(F.col("payment_timestamp")))
    # 地理異常: 遠隔地 / 正常は8割自宅一致
    REMOTE = ["北海道","青森県","沖縄県","鹿児島県","岩手県","秋田県","山形県","宮崎県"]
    pay = pay.withColumn("transaction_prefecture",
        F.when(F.col("_pat")=="地理異常",
               F.element_at(F.array(*[F.lit(p) for p in REMOTE]), (F.abs(F.hash("payment_id")) % len(REMOTE))+1))
         .when(~F.col("is_fraud"), F.when(F.rand()<0.8, F.col("home_pref")).otherwise(F.col("transaction_prefecture")))
         .otherwise(F.col("transaction_prefecture")))
    # 高額異常: 月平均の5〜10倍/日
    pay = pay.withColumn("amount",
        F.when(F.col("_pat")=="高額異常",
               F.least((F.col("avg_monthly_spend")*(F.rand()*5+5)/30).cast("int"), F.lit(500000)))
         .otherwise(F.col("amount")))
    # カードテスト: 少額
    pay = pay.withColumn("amount",
        F.when(F.col("_pat")=="カードテスト", (F.rand()*400+100).cast("int")).otherwise(F.col("amount")))
    # 乗っ取り: 新規デバイス / 正常は9割主デバイス
    pay = pay.withColumn("device_id",
        F.when(F.col("_pat")=="乗っ取り", F.concat(F.lit("DEV_NEW_"), F.substring(F.md5("payment_id"),1,8)))
         .when((~F.col("is_fraud")) & (F.rand()<0.9), F.col("primary_device_id"))
         .otherwise(F.col("device_id")))
    pay = pay.drop("_pat","home_pref","avg_monthly_spend","primary_device_id")
    pay.repartition(8).write.mode("overwrite").parquet(f"{landing}/t_payments/")

    # --- ファクト：ポイント ---
    pts = (spark.range(num_points)
        .withColumn("point_txn_id", F.format_string("PT%012d", F.col("id")))
        .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
        .withColumn("payment_id", F.format_string("PAY%012d", F.floor(F.rand()*num_payments).cast("long")))
        .withColumn("txn_type", _pick(F.col("id"), "pt", ["付与","付与","付与","利用","失効"]))
        .withColumn("points", (F.rand()*499+1).cast("int"))
        .withColumn("txn_timestamp", F.to_timestamp(F.from_unixtime(base + (F.rand()*span).cast("long"))))
        .drop("id"))
    pts = pts.withColumn("points", F.when(F.col("txn_type").isin("利用","失効"), -F.abs("points")).otherwise(F.abs("points")))
    pts = pts.withColumn("payment_id", F.when(F.col("txn_type")=="失効", F.lit(None)).otherwise(F.col("payment_id")))
    pts.repartition(4).write.mode("overwrite").parquet(f"{landing}/t_point_transactions/")

    # --- ファクト：チャージ ---
    chg = (spark.range(num_charges)
        .withColumn("charge_id", F.format_string("CHG%010d", F.col("id")))
        .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
        .withColumn("amount", _pick(F.col("id"), "chg", [1000,2000,3000,5000,10000,20000,30000,50000]))
        .withColumn("source", _pick(F.col("id"), "src", ["銀行口座","クレジットカード","ATM","ネットバンキング","オートチャージ"]))
        .withColumn("charge_timestamp", F.to_timestamp(F.from_unixtime(base + (F.rand()*span).cast("long"))))
        .withColumn("status", _pick(F.col("id"), "cst", ["成功","成功","成功","失敗"]))
        .drop("id"))
    chg.repartition(2).write.mode("overwrite").parquet(f"{landing}/t_charges/")

    # --- ファクト：ログイン ---
    lg = (spark.range(num_logins)
        .withColumn("login_id", F.format_string("LGN%012d", F.col("id")))
        .withColumn("customer_id", F.format_string("C%09d", F.floor(F.rand()*num_customers).cast("long")))
        .withColumn("login_timestamp", F.to_timestamp(F.from_unixtime(base + (F.rand()*span).cast("long"))))
        .withColumn("device_id", F.format_string("DEV%010d", F.floor(F.rand()*num_customers*2).cast("long")))
        .withColumn("device_type", _pick(F.col("id"), "ldt", DEV))
        .withColumn("login_prefecture", _pick(F.col("id"), "lpref", PREF))
        .withColumn("ip_address_masked", _ip)
        .withColumn("is_success", F.rand() >= 0.08)
        .withColumn("auth_method", _pick(F.col("id"), "am", ["パスワード","生体認証","SMS認証","パスキー"]))
        .drop("id"))
    lg.repartition(4).write.mode("overwrite").parquet(f"{landing}/t_login_events/")

    print("サンプルデータ生成 完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターテーブルの取り込み
# MAGIC `master` Volume のマスター Parquet を読み、自分のスキーマに Bronze マスターテーブルとして保存する。

# COMMAND ----------

def _table_exists(table_name: str) -> bool:
    return spark.catalog.tableExists(f"{bp}.{table_name}")

def load_master(name: str):
    target = f"bronze_{name}"
    if (not replace_master_tables) and _table_exists(target):
        print(f"スキップ（既存）: {target}")
        return
    (spark.read.parquet(f"{master}/{name}/")
        .write.mode("overwrite").saveAsTable(f"{bp}.{target}"))
    print(f"作成: {target} = {spark.table(f'{bp}.{target}').count():,} 件")

for m in ["m_customers", "m_merchants", "m_payment_methods"]:
    load_master(m)

# COMMAND ----------

# MAGIC %md
# MAGIC ## マスターへの PK 制約付与
# MAGIC 後続の Silver / Gold で FK 参照するため、マスターに主キー制約を付与する（未設定時のみ）。

# COMMAND ----------

def _pk_exists(table_name: str) -> bool:
    df = spark.sql(f"""
        SELECT 1 FROM {catalog}.information_schema.table_constraints
        WHERE table_schema='{schema}' AND table_name='{table_name}'
          AND constraint_type='PRIMARY KEY' LIMIT 1""")
    return df.count() > 0

def add_pk(table_name: str, pk_col: str):
    full = f"{bp}.{table_name}"
    if _pk_exists(table_name):
        print(f"PK 既存（スキップ）: {full}")
        return
    spark.sql(f"ALTER TABLE {full} ALTER COLUMN {pk_col} SET NOT NULL")
    spark.sql(f"ALTER TABLE {full} ADD CONSTRAINT {table_name}_pk PRIMARY KEY({pk_col})")
    print(f"PK: {full}({pk_col})")

add_pk("bronze_m_customers", "customer_id")
add_pk("bronze_m_merchants", "merchant_id")
add_pk("bronze_m_payment_methods", "method_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ 初期セットアップ完了
# MAGIC
# MAGIC ```
# MAGIC 【workspace.de_workshop】
# MAGIC   ├─ Volume : landing      … ファクト Parquet（t_*）→ この後 10_bronze が Auto Loader で取り込む
# MAGIC   ├─ Volume : master       … マスター Parquet（m_*）→ 上で Bronze 取り込み済み
# MAGIC   ├─ Volume : checkpoints  … Auto Loader チェックポイント
# MAGIC   ├─ bronze_m_customers  (PK)
# MAGIC   ├─ bronze_m_merchants  (PK)
# MAGIC   └─ bronze_m_payment_methods (PK)
# MAGIC ```
# MAGIC 10/20/30 の各ノートブックは冒頭で `%run ./05_setup` を実行し、`catalog` / `schema` / `bp` /
# MAGIC `landing` / `checkpoint_base` などを再利用する（データは生成済みなので再生成されない）。

# COMMAND ----------

print("✅ 初期セットアップ完了")
print(f"  スキーマ: {bp}")
for t in ["bronze_m_customers", "bronze_m_merchants", "bronze_m_payment_methods"]:
    if _table_exists(t):
        print(f"  {t}: {spark.table(f'{bp}.{t}').count():,} 件")
