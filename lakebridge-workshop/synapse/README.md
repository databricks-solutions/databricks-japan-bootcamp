# Synapse から Databricks への移行ハンズオン

Azure Synapse Analytics (Dedicated SQL Pool) から Databricks への移行を想定し、Lakebridge の Analyzer で規模感を掴んだ上で、**3 種類の Converter** (BladeBridge / Morpheus / Switch) で同じインプットを変換し、それぞれの強みと使い分けを体感する。

## インプット

`input/` 配下に以下を配置済み。

| ファイル | 内容 |
|---|---|
| `ddl/01_customers.sql` | テーブル DDL (HASH + CCI + DEFAULT SYSUTCDATETIME) |
| `ddl/02_products.sql` | テーブル DDL (REPLICATE) |
| `ddl/03_stores.sql` | テーブル DDL (REPLICATE + HEAP) |
| `ddl/04_orders.sql` | テーブル DDL (HASH + CCI + PARTITION RANGE RIGHT) |
| `ddl/05_order_items.sql` | テーブル DDL (HASH + CCI + 計算列 PERSISTED) |
| `stored_procs/mssql_example1_multi_statement_transformation.sql` | マルチステートメント変換 (DELETE / UPDATE / 制御フローの組み合わせ) |
| `stored_procs/mssql_example2_stored_procedure.sql` | ストアドプロシージャ (`CREATE PROCEDURE` + 動的 SQL + 変数宣言、例 1 より長め) |

## 各 Converter のサマリ

| Converter | 得意領域 | 出力形式 |
|---|---|---|
| **BladeBridge** | 幅広いソース / DDL / ETL メタデータ | `.sql` |
| **Morpheus** | mssql / snowflake / synapse 向け | `.sql` (T-SQL の構文を保持、未対応箇所は `FIXME` コメント) |
| **Switch** | 複雑なストアドプロシージャ、意味を汲んだ書き換え (計算列の型推論など) | Python Notebook (既定) |

---

## Analyzer

Analyzer は移行元コードをスキャンし、複雑度スコアを Excel レポートとして出力する。**実案件でも最初にこれを実行する**。

### 実行

まず作業ディレクトリに移動し、出力先ディレクトリを用意する:

```bash
cd lakebridge-workshop/synapse/
mkdir -p out
```

次に `analyze` のオプションを確認:

```bash
databricks labs lakebridge analyze --help
```

主要フラグ (`--source-directory` / `--report-file` / `--source-tech`) が一覧で表示される。今回は Synapse を対象にするので、以下のように実行する:

```bash
databricks labs lakebridge analyze \
  --source-directory ./input \
  --report-file ./out/synapse-report.xlsx \
  --source-tech "Synapse" \
  --profile <your-profile>
```

### 出力の確認

`out/synapse-report.xlsx` を開く。全 13 シートあるが、最初は以下を中心に見る:

| シート | 見る観点 |
|---|---|
| `Summary` | ファイル数や解析結果のサマリ |
| `SQL Programs` | ファイル 1 行 1 件、**`Complexity` (LOW / MEDIUM / HIGH)** と `Script Category` で移行難度を判断 |
| `SQL Script Categories` | 検出された SQL 構文カテゴリ一覧 |
| `UNKNOWN SQL Category` | Analyzer が解釈できなかった断片 (GO / BEGIN TRY など) |

### 学習ポイント

`Complexity` 列が LLM 要否判断の中心指標。

- DDL 5 本: いずれも **LOW**
- ストアド例 1 (`mssql_example1_multi_statement_transformation.sql`): **LOW**
- ストアド例 2 (`mssql_example2_stored_procedure.sql`): **MEDIUM** → Switch (LLM) 候補

まずは全ファイルをルールベース (BladeBridge / Morpheus) で回してみて、パース失敗や変換残差が目立つものを Switch (LLM) に切り替える、というのが基本的な進め方。

---

## Transpile: BladeBridge

BladeBridge は **正規表現ベースのルールベース**トランスパイラ (Perl + JSON config)。**幅広いソース** (Synapse / Teradata / Oracle / MSSQL / Netezza / DataStage / SSIS など) に対応し、`--overrides-file` / `--transpiler-config-path` で書換えルールをカスタマイズできる点が特徴。対応ソースの全体は `databricks labs lakebridge describe-transpile` の出力で確認できる。

### 実行

Synapse は BladeBridge と Morpheus の両方が対応しているため、`--transpiler-config-path` で BladeBridge を明示指定する:

```bash
mkdir -p out/bladebridge
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/bladebridge \
  --transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml \
  --profile <your-profile>
```

### 出力の構造

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

**別ファイルとしての変換レポートやエラーログは生成されない。** 変換結果のサマリは標準出力に 1 行テーブル (`total_files_processed / parsing_error_count / validation_error_count / generation_error_count / ...`) として表示されるのみ。

### Validator による Exception wrapping

既定では変換後 SQL を Databricks SQL Validator (profile の warehouse_id を使用) で構文チェックし、**失敗したファイルは全体が `-------------- Exception Start-------------------` / `---------------Exception End --------------------` ブロックでコメント化**され、先頭に `[PARSE_SYNTAX_ERROR]` 詳細が入る。

`--skip-validation true` を付ければ validator を通さず、生の変換 SQL をそのまま出力できる。

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

- BladeBridge は**幅広いソースに対応**している
- 変換結果がそのまま動くことも多いが、**細かいパッチ** (余計な `;` など) が残るケースが一定ある
- Synapse の T-SQL 固有構文 (`PARTITION ... RANGE RIGHT FOR VALUES`、`LineAmount AS (...) PERSISTED` 計算列) は書換えを試みた上で、validator に弾かれるケースがある

### 変換ルールのカスタマイズ (補足)

BladeBridge は 2 通りのカスタマイズ手段を提供する:

- `--overrides-file`: 既存ルール集に `line_subst` / `block_subst` の regex を**追加**する (軽い補正向け)
- `--transpiler-config-path`: 変換ルール集を**まるごと別のものに差し替える** (重い改造向け)

ソースによって config の構造が違う点に注意する。例えば Teradata は `base_teradata2databricks_sql.json` 1 ファイルに全ルールが詰まったモノリシックな構成のため `--overrides-file` でルールを追加しやすい。一方、Synapse はベースが薄めで、実ルールが `table_ddl_synapse2sparksql.json` 等に分散して Perl dispatch でロードされる構成になっている。このため Synapse に対して `--overrides-file` でルールを追加するとロード経路と衝突して空出力になるケースがある。Synapse で大きく補正を当てたい場合は `--transpiler-config-path` でカスタム config を指定する方が確実。

---

## Transpile: Morpheus

Morpheus は Databricks Labs が開発するルールベーストランスパイラ。ANTLR パーサーで SQL を構造的に解析し、**元の SQL 構文を保持しつつ `FIXME` コメントで未対応箇所を明示**するスタイル。現時点の対応方言は mssql / snowflake / synapse (今後拡張予定)。BladeBridge より対応方言は狭い。Databricks Labs が直接開発しているため改善の反映が速く、変換の実行速度も BladeBridge を上回る。

### 実行

BladeBridge と同じ要領で、`--transpiler-config-path` で Morpheus を明示指定する:

```bash
mkdir -p out/morpheus
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/morpheus \
  --transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml \
  --profile <your-profile>
```

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
| 変換速度 | 標準 | BladeBridge より速い |

### パース失敗の例 (`04_orders.sql`)

Morpheus は ANTLR パーサーで SQL を構造解析するため、T-SQL 固有構文を読み切れないと**ファイル全体がパース失敗**となり、Exception ブロックで wrap された状態で出力される。たとえば `04_orders.sql` の `PARTITION ... RANGE RIGHT FOR VALUES` は Morpheus のパーサー規則にないため `PARSE_SYNTAX_ERROR` となり、ほぼ原文のまま Exception でくるまれる。

一方、BladeBridge は正規表現ベースのため同じファイルをパターン置換で書き換えを試み、`PARTITION` 句を削除/改変して最終的に構文的に通る SQL を出力する (ただし意味が保たれるとは限らない)。両者の差は、Exception ブロックの有無と `FIXME` コメントの位置で一目で分かる。

### 学習ポイント

- **Morpheus の強み**: 速度、T-SQL 構文保持 (原文対比でレビューしやすい)、Databricks Labs が継続的に改善している
- **Morpheus の弱み**: T-SQL 固有構文 (例: `PARTITION ... RANGE RIGHT FOR VALUES`) でパース失敗するとファイル単位で Exception wrap されるため、その部分は手動で書き換える必要がある
- **使い分けは品質を見て決める**のが実務的。両方実行して diff を取るのが最速
- **Morpheus は現状、カスタマイズ口が公開されていない** (ANTLR + JAR 内蔵)。BladeBridge の `--overrides-file` のような補正機構は無い

---

## Transpile: Switch

Switch は **LLM ベース**のトランスパイラで、**Lakebridge の pluggable transpiler の 1 つ**として提供される。Databricks Job として workspace 上で走り、**既定では Python Notebook** を出力する (BladeBridge / Morpheus は `.sql` ファイル)。複雑なストアドプロシージャの変換や、構文の意味を汲んだ書き換え (計算列の型推論など) を得意とする。

利用モデルは Databricks の **基盤モデル API** の任意モデル、および Model Serving 上の外部モデルも選択可能。出力形式も設定で `.sql` / `.py` などに切り替えられる。

### 実行: `llm-transpile`

```bash
databricks labs lakebridge llm-transpile \
  --input-source ./input \
  --output-ws-folder /Workspace/Users/<your-email>/lakebridge-demo/switch-output \
  --source-dialect synapse \
  --accept-terms true \
  --profile <your-profile>
```

対話プロンプトが 4 段階続く:

| 項目 | 推奨 | 既定 |
|---|---|---|
| **catalog** | 自分の UC catalog (例: `<your_catalog>`) | `lakebridge` |
| **schema** | 既定のまま (未存在なら作成確認あり) | `switch` |
| **volume** | 既定のまま (未存在なら作成確認あり) | `switch_volume` |
| **foundation_model** | 組織で使える任意の FM (後述) | `[Recommended]` 付きのモデル |

> **Foundation Model の選び方**: 組織の Model Serving 設定 (input/output guardrail 等) によっては特定 FM で変換がブロックされる場合があるので、組織内で利用可能なものを選ぶ。

パラメータの意味:

| パラメータ | 意味 |
|---|---|
| `--input-source` | 手元の入力ディレクトリ (自動で Unity Catalog Volume にアップロード) |
| `--output-ws-folder` | Databricks Workspace 上の出力パス (必ず　`/Workspace/` で始まる必要がある) |
| `--source-dialect` | `synapse` |
| `--accept-terms` | LLM ベース変換の利用規約に同意 (`true`) |

実行すると Switch Job が起動し、Job URL が返る (非同期):

```
INFO [d.l.l.transpiler.switch_runner] Uploading input to /Volumes/<catalog>/switch/switch_volume/input-<ts>-<id>...
INFO [d.l.l.transpiler.switch_runner] Upload complete
INFO [d.l.l.transpiler.switch_runner] Triggering Switch job with job_id: <switch_job_id>
INFO [d.l.l.transpiler.switch_runner] Switch LLM transpilation job started: https://<workspace>/jobs/<id>/runs/<id>
```

### Job の進捗を監視

返された Job URL を開いて Switch Job の run を監視。LLM が並列呼び出しするため所要時間はファイル本数に比例しない。本 Lab 程度なら数分のオーダーで完了することが多い。

Switch は workspace 内 **結果テーブル** (`<catalog>.switch.lakebridge_switch_<timestamp>_<suffix>`) にも全ファイルの変換結果を記録しており、そちらを SELECT すれば進捗/エラーも確認できる。結果テーブルのスキーマは公式ドキュメント [Customizing Switch](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/customizing_switch/) を参照。

> **Job の `result_state: SUCCESS` はファイル単位の成功を保証しない**。必ず結果テーブルの `export_status = 'exported'` 件数で確認する。

### 変換結果を確認

`--output-ws-folder` 配下に **Python Notebook** が出力される。Workspace UI で開いて確認:

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

**Switch の真価**: `05_order_items.sql` の `LineAmount AS (Quantity * UnitPrice - DiscountAmount) PERSISTED` (T-SQL 計算列、型指定なし) を **`DECIMAL(18,2) GENERATED ALWAYS AS (...)` に型推論込みで変換**。これは BladeBridge / Morpheus の regex では書けない、構文の意味を汲んだ書き換え。

### 学習ポイント

- **Switch の強み**: LLM が構文の意図を読んで書き直すため、ルールベースでは詰まる複雑なストアドプロシージャや、意味を汲んだ書き換え (計算列の型推論など) を 1 発変換で狙える
- **Switch の弱み**: LLM 呼び出しコスト、非決定性 (再実行で微妙に差分)、レビュー必須
- **カスタマイズ**: `concurrency` / `token_count_threshold` / カスタムプロンプトなどは Workspace 上の `switch_config.yml` で調整可能。詳細は [Customizing Switch](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/customizing_switch/) を参照

---

## 3 種 Converter 比較まとめ

| 観点 | BladeBridge | Morpheus | Switch |
|---|---|---|---|
| 出力形式 | `.sql` | `.sql` (T-SQL の構文を保持 + FIXME) | Notebook (既定、他形式にも設定可) |
| 速度 | ○ | ◎ | △ (LLM 呼出) |
| 決定性 | ◎ | ◎ | △ (再実行で差分あり) |
| カスタマイズ | `--overrides-file` / `--transpiler-config-path` | 現状未公開 | `switch_config.yml` + カスタムプロンプト |
| 得意領域 | 幅広いソース | mssql / snowflake / synapse | 複雑なストアドプロシージャ、意味を汲んだ書き換え |

**使い分けの方針:**

- 定型 SQL (DDL / 単純クエリ) はルールベース (BladeBridge / Morpheus) で速く回す
- 複雑なストアドプロシージャ (動的 SQL / TRY-CATCH など) や、計算列の型推論のように意味を汲んだ書き換えが必要なものは Switch の利用を検討
