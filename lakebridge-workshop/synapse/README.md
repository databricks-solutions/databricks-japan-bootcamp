# Synapse → Databricks ハンズオン

Azure Synapse Analytics (Dedicated SQL Pool) から Databricks への移行を想定し、Lakebridge の Analyzer で規模感を掴んだ上で、**3 種類の Converter** (BladeBridge / Morpheus / Switch) で同じインプットを変換し、それぞれの強みと使い分けを体感する。

所要目安: 約 50 分 (Analyzer 5 分 + BladeBridge 5 分 + Morpheus 3 分 + Switch 15 分)

## インプット

`input/` 配下に以下を配置済み。

```
input/
├── ddl/                                               # 自作 5 テーブル (Synapse 固有構文)
│   ├── 01_customers.sql                               # HASH + CCI + DEFAULT SYSUTCDATETIME
│   ├── 02_products.sql                                # REPLICATE
│   ├── 03_stores.sql                                  # REPLICATE + HEAP
│   ├── 04_orders.sql                                  # HASH + CCI + PARTITION RANGE RIGHT
│   └── 05_order_items.sql                             # HASH + CCI + 計算列 (PERSISTED)
└── stored_procs/                                      # Switch 公開サンプル 2 本
    ├── mssql_example1_multi_statement_transformation.sql
    └── mssql_example2_stored_procedure.sql
```

Synapse と T-SQL のストアドは Lakebridge 的には同じ `synapse` dialect で扱える (ストアド側には HASH/REPLICATE は出てこないが、T-SQL 構文は共通)。

## 各 Converter の使い分け (先取り)

| Converter | ベース | 得意領域 | 出力形式 |
|---|---|---|---|
| **BladeBridge** | ルールベース (Perl) | 幅広い dialect / DDL / ETL メタデータ | `.sql` (Databricks 方言に積極書換え) |
| **Morpheus** | ルールベース (ANTLR パーサー、Databricks 純正) | mssql / snowflake / synapse に特化 | `.sql` (T-SQL 原文寄りを保持 + `FIXME` コメント) |
| **Switch** | LLM (Claude Sonnet 系) | 複雑ストアド、意味変換 (計算列等) | `.py` Python Notebook (workspace にデプロイ) |

---

## 1. Analyzer

Analyzer は移行元コードをスキャンし、複雑度スコアを Excel レポートに吐き出す。**実案件では最初にこれを走らせる**。

### 実行

`lakebridge-workshop/synapse/` に居る前提。

```bash
databricks labs lakebridge analyze \
  --source-directory ./input \
  --report-file ./out/synapse-report.xlsx \
  --source-tech "Synapse" \
  --profile <your-profile>
```

`--source-tech` は大文字先頭でも小文字でもいけるケースが多い (実際に `Synapse` で受理される)。`analyze --help` で対応値を確認できる。

### 生成物の確認

`out/synapse-report.xlsx` を開く。中には **13 シート**あり、主に以下を見る:

| シート | 見る観点 |
|---|---|
| `Summary` | ファイル数 (Total SQL Scripts / Procedures / Tables) / 解析結果サマリ |
| `SQL Programs` | ファイル 1 行 1 件、**`Complexity` (LOW / MEDIUM / HIGH)** と `Script Category` で移行難度を判断 |
| `SQL Script Categories` | 検出された SQL 構文カテゴリ一覧 (CREATE_PROCEDURE / DYNAMIC_SQL / FOR / IF_START / UPDATE_FROM 等) |
| `UNKNOWN SQL Category` | Analyzer が解釈できなかった断片 (GO、BEGIN TRY、COMMIT TRAN 等) |
| `SQL Special Patterns` | 特殊パターン (本 Lab では空) |
| `Functions`, `Functions by Script`, `Scripts Functions Xref` | 関数呼び出し集計 (CONVERT / NVARCHAR / SYSUTCDATETIME 等) |
| `Referenced Objects`, `Program-Object Xref`, `RAW_PROGRAM_OBJECT_XREF` | テーブル/オブジェクト参照 |
| `RAW_PROGRAM_PARAM_LIST` | ストアドプロシージャのパラメータ一覧 |
| `SQL Data Types` | DDL で使われている型の集計 |

### 学習ポイント

**`Complexity` 列が LLM 要否判断の中心指標。**

- `mssql_example2_stored_procedure.sql` (Statement=33、**Complexity=MEDIUM**、Medium category breaks=1、CREATE_PROCEDURE / DYNAMIC_SQL / IF_START / VAR_DECLARE 含む) → **Switch (LLM) 候補**
- `mssql_example1_multi_statement_transformation.sql` (Statement=9、**Complexity=LOW**、DELETE / UPDATE_FROM / IF_START 含む) → ルールベースでもいけそうだが要レビュー
- DDL 5 本はいずれも Complexity=LOW → ルールベース (BladeBridge / Morpheus) で回す

`llm_support_needed` 列は Analyzer 出力には**存在しない**。Complexity + Script Category の組み合わせで判断する。

### トラブルシュート

- `analyze` が途中で止まる → `--source-directory` を絶対パスで指定すると安定する
- Excel が開けない → Mac の「プレビュー」では Excel 読めない、Numbers / Excel 本体 / Google Sheets 等を使う

---

## 2. Transpile: BladeBridge

BladeBridge は Travinto Technologies 由来のルールベーストランスパイラ (Perl + JSON config)。**広い source dialect** (datastage / ssis / synapse / teradata / oracle / netezza / redshift / mssql / informatica 等) に対応。**積極的に Databricks 方言へ書き換える**スタイル。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/bladebridge \
  --profile <your-profile>
```

`Multiple transpilers available for dialect 'synapse': frozenset({'Morpheus', 'Bladebridge'})` と出て対話プロンプトになるので **Bladebridge** を選ぶ。

> 非対話モードで固定したい時は `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml` を追加。

### 生成物の構造

```
out/bladebridge/
├── ddl/
│   ├── 01_customers.sql
│   ├── 02_products.sql
│   └── ... (5 file、入力のサブディレクトリ構造を保持)
└── stored_procs/
    ├── mssql_example1_multi_statement_transformation.sql
    └── mssql_example2_stored_procedure.sql
```

**report や error log の別ファイルは出力されない**。変換サマリは stdout の 1 行テーブル (`total_files_processed / parsing_error_count / validation_error_count / generation_error_count / ...`) だけ。

### Validator による Exception wrapping

既定では変換後 SQL を Databricks SQL Validator (profile の warehouse_id を使用) に投げ、**失敗したファイルは全体が `-------------- Exception Start-------------------` / `---------------Exception End --------------------` ブロックでコメント化**され、先頭に `[PARSE_SYNTAX_ERROR]` 詳細が入る。

検証を外して**生の変換 SQL** を見たい場合:

```bash
databricks labs lakebridge transpile ... --skip-validation true ...
```

### 出力を観察

`02_products.sql` (validation を通る clean ケース) と `01_customers.sql` (validation 失敗ケース) を開き比較する。

**clean ケース (02_products):**

```sql
CREATE OR REPLACE TABLE dbo.products
(
    ProductID       INT             NOT NULL,
    ProductName STRING   NOT NULL,            -- NVARCHAR → STRING
    CategoryCode STRING     NOT NULL,
    UnitPrice       DECIMAL(19,4)           NOT NULL,
    Barcode STRING,
    LaunchedAt      DATE,
    DiscontinuedAt  DATE
);
```

- `NVARCHAR`/`VARCHAR` → `STRING`
- `CREATE TABLE` → `CREATE OR REPLACE TABLE`
- `WITH (DISTRIBUTION = REPLICATE)` は削除

**validation 失敗ケース (01_customers):**

Exception ブロックの中身に注目すると、変換 SQL 自体は生成されているが、末尾に余計な `;` が入って validator に弾かれている:

```sql
RegisteredAt    timestamp    NOT NULL DEFAULT current_timestamp();,
-- ^^^ この ; が余計
LastUpdatedAt   timestamp    NOT NULL DEFAULT current_timestamp();,
```

### 学習ポイント

- BladeBridge は**広い dialect カバレッジ** + **Databricks 方言への積極書換え**
- 変換結果がそのまま走ることも多いが、**細かいパッチ** (余計な `;` など) が残るケースが一定ある
- Synapse の T-SQL 固有構文 (`PARTITION ... RANGE RIGHT FOR VALUES`、`LineAmount AS (...) PERSISTED` 計算列) は書換えを試みた上で、validator に弾かれるケースがある

### Override による修正 (補足)

BladeBridge は `--overrides-file` で `line_subst` / `block_subst` の regex を追加できる。ただし **Synapse dialect の override は現時点で制約が多い** (root config (`base_synapse2databricks_sql.json`) が 5 行と薄く、DDL 変換ルールは別ファイル (`table_ddl_synapse2sparksql.json`) の Perl dispatch 依存で、`--overrides-file` 指定だとこの dispatch が壊れて空出力になる現象を確認)。**Teradata などの monolithic config を持つ dialect では override が素直に動く**ため、そちらで活用するのが実務的。

---

## 3. Transpile: Morpheus

Morpheus は Databricks 純正 (Databricks Labs) のルールベーストランスパイラで、**mssql / snowflake / synapse の 3 方言に特化**。ANTLR パーサーで T-SQL を構造的に解析し、**T-SQL 原文寄りの形を保持しつつ `FIXME` コメントで未対応箇所を明示**するスタイル。BladeBridge よりカバレッジは狭いが、純正ゆえに追従速度が速く、速度も桁違いに速い。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/morpheus \
  --profile <your-profile>
```

対話プロンプトで **Morpheus** を選ぶ。非対話なら `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml`。

### BladeBridge との差を見る

```bash
diff -u ./out/bladebridge/ddl/02_products.sql ./out/morpheus/ddl/02_products.sql
```

Morpheus の `02_products.sql` (同じく clean):

```sql
CREATE
    /* DISTRIBUTION = REPLICATE CLUSTERED INDEX (ProductID) */
    -- FIXME: ^^^ The above create table options are unsupported
    TABLE dbo.products
    (
        ProductID INT NOT NULL,
        ProductName VARCHAR(300) NOT NULL,        -- VARCHAR を保持
        CategoryCode VARCHAR(20) NOT NULL,
        UnitPrice DECIMAL(19, 4) NOT NULL,
        Barcode VARCHAR(13),
        LaunchedAt DATE,
        DiscontinuedAt DATE
    );
```

**スタイルの違い:**

| 観点 | BladeBridge | Morpheus |
|---|---|---|
| `CREATE TABLE` | `CREATE OR REPLACE TABLE` に書き換え | そのまま保持 |
| 型 (`NVARCHAR/VARCHAR`) | `STRING` に書き換え | `VARCHAR(n)` 保持 (Databricks でも受理) |
| 非対応構文 (`DISTRIBUTION`) | 削除 | `/* ... */ FIXME` コメント |
| 変換速度 (7 file) | ~80 秒 | ~9 秒 |

### 学習ポイント

- **Morpheus の強み**: 速度、T-SQL 構文保持 (原文対比レビューしやすい)、純正ゆえの継続改善
- **Morpheus の弱み**: T-SQL 固有構文 (例: `PARTITION ... RANGE RIGHT FOR VALUES`) で**パース失敗**し、ファイルが Exception wrap される (04_orders.sql で発生)。一方 BladeBridge は regex で書き換えを試みて通すケースがある
- **使い分けは品質を見て決める**のが実務的。両方走らせて diff を取るのが最速
- **Morpheus はカスタマイズができない** (ANTLR + JAR 内蔵)。BladeBridge の `--overrides-file` のような補正機構は無い

---

## 4. Transpile: Switch

Switch は LLM ベース (Foundation Model API / Claude Sonnet) のトランスパイラで、**Lakebridge の pluggable transpiler の 1 つ**として提供される。Databricks Job として workspace 上で走り、**Python Notebook** を出力する (Bladebridge/Morpheus は `.sql` ファイル)。複雑ストアドや意味変換 (計算列の型推論等) に強い。

### 1. Switch がインストールされているか確認

Switch は `describe-transpile` には**出ない** (BladeBridge/Morpheus とはアーキテクチャが違うため)。トップ README の [前提セットアップ](../README.md#4-transpiler-プラグインのインストール) で `install-transpile` を **`--include-llm-transpiler true`** 付きで実行していれば workspace に Job + Notebook がデプロイされているはず。

確認するなら:

```bash
databricks workspace list /Users/<your-email>/.lakebridge/switch --profile <your-profile>
```

`resources/switch_config.yml` 等が並んでいれば OK。

### 2. Workspace 側の出力フォルダを事前作成

Switch は `--output-ws-folder` 配下に**入力のサブディレクトリ構造を再帰的に作らない**ため、入力が `ddl/` と `stored_procs/` の 2 サブディレクトリなら両方を事前作成しておく:

```bash
databricks workspace mkdirs /Workspace/Users/<your-email>/lakebridge-demo/switch-output/ddl --profile <your-profile>
databricks workspace mkdirs /Workspace/Users/<your-email>/lakebridge-demo/switch-output/stored_procs --profile <your-profile>
```

### 3. `llm-transpile` で変換実行

```bash
databricks labs lakebridge llm-transpile \
  --input-source ./input \
  --output-ws-folder /Workspace/Users/<your-email>/lakebridge-demo/switch-output \
  --source-dialect synapse \
  --accept-terms true \
  --profile <your-profile>
```

対話プロンプトが 4 段階続く:

| 項目 | 既定 | 推奨 |
|---|---|---|
| **catalog** | `lakebridge` | 自分の UC catalog (例: `<your_catalog>`) |
| **schema** | `switch` | 既定のまま (未存在なら作成確認あり) |
| **volume** | `switch_volume` | 既定のまま (未存在なら作成確認あり) |
| **foundation_model** | 38 候補から選択 | **必ず `[0] [Recommended] databricks-claude-sonnet-4-5`** |

> **Foundation Model は `[Recommended]` 印のある `databricks-claude-sonnet-4-5` を選ぶ。** 組織の Model Serving 設定 (input/output guardrail 等) によっては他 FM で変換がブロックされる場合があるため、当面は Recommended に従うのが無難。

パラメータの意味:

| パラメータ | 意味 |
|---|---|
| `--input-source` | 手元の入力ディレクトリ (自動で Unity Catalog Volume にアップロード) |
| `--output-ws-folder` | Databricks Workspace 上の出力パス (`/Workspace/` 始まり必須) |
| `--source-dialect` | `synapse` |
| `--accept-terms` | LLM ベース変換の利用規約に同意 (`true`) |

実行すると Switch Job が起動し、Job URL が返る (非同期):

```
INFO [d.l.l.transpiler.switch_runner] Uploading input to /Volumes/<catalog>/switch/switch_volume/input-<ts>-<id>...
INFO [d.l.l.transpiler.switch_runner] Upload complete
INFO [d.l.l.transpiler.switch_runner] Triggering Switch job with job_id: <switch_job_id>
INFO [d.l.l.transpiler.switch_runner] Switch LLM transpilation job started: https://<workspace>/jobs/<id>/runs/<id>
```

### 4. Job の進捗を監視

返された Job URL を開いて Switch Job の run を監視。ファイル数 × LLM 呼び出しのため、DDL + ストアド 7 本で **3〜5 分**程度。

Switch は workspace 内 **結果テーブル** (`<catalog>.switch.lakebridge_switch_<timestamp>_<suffix>`) にも全ファイルの変換結果を記録する。Job URL を見なくても結果テーブルを SELECT すれば進捗/エラー確認可:

```sql
SELECT input_file_relative_path, is_conversion_target, export_status,
       LEFT(COALESCE(export_error, result_error, ''), 200) as err_short,
       result_total_tokens, result_processing_time_seconds
FROM <catalog>.switch.lakebridge_switch_<timestamp>_<suffix>
ORDER BY input_file_path;
```

> **Job の `result_state: SUCCESS` はファイル単位の成功を保証しない**。必ず結果テーブルの `export_status = 'exported'` 件数で確認する。

### 5. 生成物を確認

`--output-ws-folder` 配下に **Python Notebook** が出力されている (`.sql` ではない)。Workspace UI で開いて確認:

```python
# Databricks notebook source
# MAGIC %md
# MAGIC # 05_order_items
# MAGIC This notebook was automatically converted from the script below. ...
# COMMAND ----------
spark.sql("""
CREATE TABLE IF NOT EXISTS dbo.order_items (
    OrderID LONG NOT NULL,
    ...
    LineAmount DECIMAL(18,2) GENERATED ALWAYS AS (Quantity * UnitPrice - DiscountAmount)
    -- ^^^ Switch が型推論込みで T-SQL の "AS (...) PERSISTED" を Databricks 構文に変換
)
""")
```

**Switch の真価**: `05_order_items.sql` の `LineAmount AS (Quantity * UnitPrice - DiscountAmount) PERSISTED` (T-SQL 計算列、型指定なし) を **`DECIMAL(18,2) GENERATED ALWAYS AS (...)` に型推論込みで変換**。これは BladeBridge/Morpheus では単純な regex で書けない意味変換。

### 6. 学習ポイント

- **Switch の強み**: LLM が構文の意図を読んで書き直すため、ルールベースでは詰まる複雑ストアドや意味変換 (計算列の型推論等) で 1 発変換を狙える
- **Switch の弱み**: LLM 呼び出しコスト、非決定性 (再実行で微妙に差分)、レビュー必須、FM のガードレール誤判定リスク
- **使い分けの勘所**:
  - Analyzer で **Complexity=MEDIUM/HIGH** のファイルを Switch に回す
  - DDL や定型 SQL (Complexity=LOW) はルールベース (BladeBridge / Morpheus) が速くて確実
  - 複雑ストアド (動的 SQL / TRY-CATCH / sp_executesql) は Switch 必須
- **カスタマイズ**: `concurrency` / `token_count_threshold` / カスタムプロンプトなどは Workspace 上の `switch_config.yml` で調整可能 (ただし catalog/schema/volume/FM は `switch_config.yml` ではなく実行時の `llm-transpile` 引数/対話で指定)。詳細は [Switch 公式 Docs](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/)

---

## 3 種 Converter 比較まとめ

3 つの出力を並べて見ると:

| 観点 | BladeBridge | Morpheus | Switch |
|---|---|---|---|
| 出力形式 | `.sql` (Databricks 方言に書換え) | `.sql` (T-SQL 保持 + FIXME) | `.py` Notebook (`spark.sql("""...""")`) |
| DDL 5 本 | validator で 3/5 fail (余計な `;` 等) | validator で 2/5 fail (T-SQL 固有構文) | 型推論込みで 5/5 通る |
| ストアド example1 | 部分変換 | 部分変換 | フル変換狙える |
| ストアド example2 (複雑) | 部分変換 | パース失敗ありえる | **意味理解して書換え** |
| 決定性 | 高 | 高 | 中 (再実行で差分) |
| 速度 (7 file) | 約 80 秒 | 約 9 秒 | 約 3〜5 分 (LLM 呼出) |
| カスタマイズ | `--overrides-file` (dialect により制約あり) | 不可 | `switch_config.yml` (runtime 設定) + カスタムプロンプト |
| コスト | 低 | 低 | 中 (LLM 呼出) |

**使い分けの腹落ちポイント:**

- **ルールベース (BladeBridge / Morpheus) を先に、複雑なものだけ Switch に回す**
- BladeBridge は **幅広 dialect とカスタマイズ性**で効く (DataStage / Teradata 等)
- Morpheus は **高速・原文保持でレビューしやすい** が非対応構文が多め
- Switch は **意味変換と複雑ストアド**に強いが、レビューとコストが必要

## 次

[reconcile/](../reconcile/) で移行前後の差分検証を試す。
