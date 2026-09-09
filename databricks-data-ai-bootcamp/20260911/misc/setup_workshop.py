# Databricks notebook source

# MAGIC %md
# MAGIC # Workshop setup (Free Edition) — 固定スキーマ `workspace.de_workshop`
# MAGIC
# MAGIC Databricks **Free Edition** での単独実行用セットアップです。冪等（再実行しても安全）。
# MAGIC 複数人共有の Vocareum 環境ではないため、ユーザーごとの USER_ID や共有 `ops_data`
# MAGIC カタログは使わず、すべてを**固定スキーマ**に統一します。
# MAGIC
# MAGIC - **カタログ**: `workspace`（Free Edition の既定カタログ）
# MAGIC - **スキーマ**: `de_workshop`
# MAGIC - **Volume**: `workspace.de_workshop.landing`
# MAGIC
# MAGIC この notebook がやること:
# MAGIC 1. スキーマ `workspace.de_workshop`（if not exists）
# MAGIC 2. マネージド Volume `workspace.de_workshop.landing`（if not exists）
# MAGIC 3. その Volume の `booking_fraud_flags/` に、`samples.wanderbricks.booking_updates` の
# MAGIC    distinct な `booking_id` の **3%** を不正マーカー JSONL として投入（Lab 2 のソース）

# COMMAND ----------

dbutils.widgets.text("fraud_pct", "3.0", "% of bookings to flag as fraud")
dbutils.widgets.text("num_files", "5", "Number of JSONL files to split the seed across")

# Free Edition 固定値
CATALOG = "workspace"
SCHEMA  = "de_workshop"

try:
    FRAUD_PCT = float(dbutils.widgets.get("fraud_pct"))
except ValueError as e:
    raise ValueError("Set 'fraud_pct' to a numeric percentage, e.g. 3.0.") from e

try:
    NUM_FILES = int(dbutils.widgets.get("num_files"))
except ValueError as e:
    raise ValueError("Set 'num_files' to a positive integer, e.g. 5.") from e

if not 0.0 <= FRAUD_PCT <= 100.0:
    raise ValueError("Set 'fraud_pct' between 0 and 100.")
if NUM_FILES < 1:
    raise ValueError("Set 'num_files' to at least 1.")

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/landing/booking_fraud_flags"

print(f"catalog={CATALOG}  schema={SCHEMA}  fraud_pct={FRAUD_PCT}%  num_files={NUM_FILES}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. スキーマとランディング Volume を作成（冪等）

# COMMAND ----------

# `workspace` は Free Edition の既定カタログ（作成不要）。スキーマと Volume のみ用意する。
spark.sql(
    f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} "
    f"COMMENT 'Lakeflow DataEng Workshop (Free Edition) — 固定スキーマ'"
)
spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.landing "
    f"COMMENT 'ワークショップのシードデータ用ランディング Volume'"
)

dbutils.fs.mkdirs(VOLUME_PATH)
print(f"Volume folder ready: {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 不正マーカーを投入（bookings の 3% を JSONL で書き込み）
# MAGIC
# MAGIC 再実行するとシードファイルを上書きし、常に一貫したセットになります。

# COMMAND ----------

from pyspark.sql import functions as F

REASONS = [
    "velocity_check_failed",
    "stolen_card_report",
    "unusual_location",
    "device_fingerprint_mismatch",
    "suspicious_pattern",
]

bookings = (
    spark.table("samples.wanderbricks.booking_updates")
    .select("booking_id")
    .distinct()
)

fraction = FRAUD_PCT / 100.0
flagged = (
    bookings.sample(withReplacement=False, fraction=fraction, seed=42)
    .withColumn("flag", F.lit("fraud"))
    .withColumn(
        "reason",
        F.element_at(F.array(*[F.lit(r) for r in REASONS]),
                     (F.abs(F.hash("booking_id")) % len(REASONS)) + 1),
    )
    .withColumn(
        "flagged_at",
        F.date_format(
            F.expr("current_timestamp() - make_interval(0, 0, 0, abs(hash(booking_id)) % 90)"),
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
        ),
    )
    .withColumn(
        "confidence",
        F.round(F.lit(0.70) + (F.abs(F.hash("booking_id")) % 3000) / 10000.0, 4),
    )
)

marker_count = flagged.count()
print(f"Generated {marker_count} fraud markers ({FRAUD_PCT}% of distinct bookings)")

# COMMAND ----------

# Clear any prior seed files so re-runs produce a clean directory, then write JSONL.
for f in dbutils.fs.ls(VOLUME_PATH):
    if f.name.endswith(".json") or f.name.startswith("_"):
        dbutils.fs.rm(f.path)

(flagged
    .repartition(NUM_FILES)
    .write
    .mode("overwrite")
    .format("json")
    .save(VOLUME_PATH))

# Rename part-*.json files so the directory stays tidy (Auto Loader reads either form).
for f in dbutils.fs.ls(VOLUME_PATH):
    if f.name.startswith("part-") and f.name.endswith(".json"):
        idx = f.name.split("-")[1]
        dbutils.fs.mv(f.path, f"{VOLUME_PATH}/fraud_markers_{idx}.json")
    elif f.name.startswith("_"):
        dbutils.fs.rm(f.path)

print("Seed files written:")
for f in dbutils.fs.ls(VOLUME_PATH):
    print(f"  {f.name}  ({f.size} bytes)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 検証

# COMMAND ----------

sample = (
    spark.read.format("json")
    .load(VOLUME_PATH)
    .limit(5)
)
display(sample)

total = spark.read.format("json").load(VOLUME_PATH).count()
print(f"Total markers in volume: {total}")
print(f"Expected ~{int(47726 * FRAUD_PCT / 100)} at {FRAUD_PCT}% of ~47,726 distinct bookings")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 70)
print("WORKSHOP SETUP (Free Edition) — SUMMARY")
print("=" * 70)
print(f"Catalog       : {CATALOG}")
print(f"Schema        : {CATALOG}.{SCHEMA}")
print(f"Landing volume: {CATALOG}.{SCHEMA}.landing")
print(f"Fraud markers : {VOLUME_PATH}  ({total} rows)")
print(f"Source        : samples.wanderbricks.booking_updates ({FRAUD_PCT}% flagged)")
print("=" * 70)
