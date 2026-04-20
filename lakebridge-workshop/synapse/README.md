# Synapse → Databricks ハンズオン

Azure Synapse Analytics (Dedicated SQL Pool) から Databricks への移行を想定し、Lakebridge の Analyzer で規模感を掴んだ上で、**3 種類の Converter** (BladeBridge / Morpheus / Switch) で同じインプットを変換し、それぞれの強みと使い分けを体感する。

所要目安: 約 50 分 (Analyzer 13 分 + 各 Converter 10〜17 分)

## インプット

`input/` 配下に以下を配置済み。

```
input/
├── ddl/                                               # 自作 5 テーブル (Synapse 固有構文)
│   ├── 01_customers.sql                               # HASH + CCI
│   ├── 02_products.sql                                # REPLICATE
│   ├── 03_stores.sql                                  # REPLICATE + HEAP
│   ├── 04_orders.sql                                  # HASH + CCI + PARTITION
│   └── 05_order_items.sql                             # HASH + CCI + 計算列
└── stored_procs/                                      # Switch 公開サンプル 2 本
    ├── mssql_example1_multi_statement_transformation.sql
    └── mssql_example2_stored_procedure.sql
```

Synapse と T-SQL のストアドは Lakebridge 的には同じ `synapse` dialect で扱える (ストアド側には HASH/REPLICATE は出てこないが、T-SQL 構文は共通)。

## 各 Converter の使い分け (先取り)

| Converter | ベース | 得意領域 | このシナリオで体感 |
|---|---|---|---|
| **BladeBridge** | ルールベース | ETL メタデータ、DDL、定型変換 | DDL の変換結果をまず確認 |
| **Morpheus** | ルールベース (Databricks 純正) | mssql / snowflake / synapse に特化 | BladeBridge との差分を比較 |
| **Switch** | LLM ベース (Claude Sonnet) | 複雑ストアド、例外的な構文 | ストアドの変換品質を観察 |

---

## 1. Analyzer

Analyzer は移行元コードをスキャンし、複雑度スコア・変換難易度・推奨 Converter を Excel レポートに吐き出す。**実案件では最初にこれを走らせる**。

### 実行

`lakebridge-workshop/synapse/` に居る前提。

```bash
databricks labs lakebridge analyze \
  --source-directory ./input \
  --report-file ./out/synapse-report.xlsx \
  --source-tech "Synapse"
```

プロンプトで `Select the source technology:` が出たら `Synapse` を選ぶ (`--source-tech` を明示すればプロンプトは出ない)。

> 対応 source-tech 一覧は `databricks labs lakebridge analyze --help` で確認できる。

### 生成物の確認

```
out/
└── synapse-report.xlsx
```

Excel を開いて以下の観点でざっと眺める:

- **Summary**: ファイル数、総行数、言語ミックス、推定工数レンジ
- **FileAnalysis** 系: ファイル単位のスコア (`complexity_score`, `llm_support_needed`, `sql_dialect`)
- **Unsupported Constructs** 系: そのままでは変換できない構文リスト

### 学習ポイント

- DDL 5 本はスコアが低く、ルールベース (BladeBridge / Morpheus) で問題なく回る想定
- ストアド 2 本、特に `mssql_example2_stored_procedure.sql` (動的 SQL + TRY/CATCH + sp_executesql) はスコアが跳ね上がる → **Switch (LLM) を充てる判断根拠**になる
- 実案件ではこのレポートをレビューし、「このファイルは Switch、こっちは BladeBridge で」と方針を握る

### トラブルシュート

- `analyze` が途中で止まる → `--source-directory` を絶対パスで指定すると安定する
- Excel が開けない → `pip show openpyxl` で確認 (Lakebridge が出力に使用)

---

## 2. Transpile: BladeBridge

BladeBridge は Travinto Technologies 由来のルールベーストランスパイラ。**広い source dialect** (datastage / ssis / synapse / teradata / oracle / netezza / redshift ...) に対応しており、ETL メタデータや DDL、定型 SQL の変換が得意。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/bladebridge
```

`Select the transpiler:` プロンプトが出るので **Bladebridge** を選ぶ (Morpheus も synapse に対応しているため候補は 2 つ出る)。

> 非インタラクティブ時は `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml`

### 生成物の確認

```
out/bladebridge/
├── ddl/
│   ├── 01_customers.sql
│   ├── 02_products.sql
│   └── ...
├── stored_procs/
│   ├── mssql_example1_multi_statement_transformation.sql
│   └── mssql_example2_stored_procedure.sql
└── transpile-report.json
```

#### DDL の変換結果を観察

`out/bladebridge/ddl/01_customers.sql` を開き、元ファイルと見比べる:

- `NVARCHAR` → `STRING`、`DATETIME2` → `TIMESTAMP` など型マッピング
- `WITH (DISTRIBUTION = HASH(...), CLUSTERED COLUMNSTORE INDEX)` の扱い (Databricks では不要なため削除 or コメント化)
- `DEFAULT SYSUTCDATETIME()` → `DEFAULT CURRENT_TIMESTAMP()` 近辺
- `CREATE STATISTICS` は Databricks に概念がない → コメントアウト or スキップ

#### ストアドの変換結果を観察

`out/bladebridge/stored_procs/mssql_example2_stored_procedure.sql` は**部分変換になる可能性が高い**。`sp_executesql` / 動的 SQL / `TRY/CATCH` は Databricks SQL に単純翻訳できない。

生成ファイル内の `-- UNSUPPORTED:` コメントや、`transpile-report.*` の**変換不可箇所**を確認。

### 学習ポイント

- **DDL / 定型 SQL**: ルールベースで高速・決定論的に変換
- **複雑ストアド**: ルールベースの限界。Switch (LLM) の出番
- 案件では「DDL は BladeBridge で一気に、ストアドは Switch で個別に」という役割分担が定石

---

## 3. Transpile: Morpheus

Morpheus は Databricks 純正 (Databricks Labs) のルールベーストランスパイラで、**mssql / snowflake / synapse の 3 方言に特化**。BladeBridge より対応 dialect は狭いが、純正ゆえに追従速度が速く、Synapse → Databricks の定番ペアでは品質が期待できる。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/morpheus
```

`Select the transpiler:` プロンプトで **Morpheus** を選ぶ。

> 非インタラクティブ時は `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml`

### BladeBridge との diff を取る

```bash
diff -r ./out/bladebridge/ddl ./out/morpheus/ddl | head -80
diff ./out/bladebridge/stored_procs/mssql_example2_stored_procedure.sql \
     ./out/morpheus/stored_procs/mssql_example2_stored_procedure.sql | head -80
```

観察ポイント:

- DDL の整形方式 (改行、インデント、コメント保持)
- 型マッピングの差 (`MONEY` の扱い、`DECIMAL` の精度、`BIT` → `BOOLEAN` など)
- Synapse 固有構文 (`DISTRIBUTION`, `CLUSTERED COLUMNSTORE INDEX`, `PARTITION ... RANGE RIGHT FOR VALUES`) のコメント化 / 削除方針
- ストアド内の T-SQL 構文 (`DECLARE @var`, `SET @SQL`) のアプローチ

### 学習ポイント

- Morpheus は **Synapse → Databricks の定番ペアで継続改善される** (Databricks Labs がメンテ)
- BladeBridge は **広いカバレッジと歴史** があり、DataStage / Teradata のような Morpheus 非対応の dialect で効く
- 同じ Synapse でも、**プロジェクトによってどちらを選ぶかは品質を見てから決める**のが実務的。両方走らせて diff を取るのが最速

---

## 4. Transpile: Switch

Switch は LLM ベース (Foundation Model API / Claude Sonnet) のトランスパイラで、**Lakebridge の pluggable transpiler の 1 つ**として提供される。ルールベースで詰まる複雑ストアドに強く、任意の source dialect に対応できる柔軟性が売り。Databricks Job として動作するため、ローカル CLI ではなくワークスペース上で実行する。

### 1. Switch がインストールされているか確認

トップ README の [前提セットアップ](../README.md#前提セットアップ) の手順で `install-transpile` の **`All`** を選んでいれば Switch も入っている。

```bash
databricks labs lakebridge describe-transpile
```

出力に `name: Switch` が含まれることを確認。無ければ `install-transpile --profile DEFAULT` を再実行して `All` を選ぶ。

### 2. インプットをワークスペースの Volume にアップロード

Unity Catalog Volume を SQL Editor で作成 (未作成の場合):

```sql
CREATE VOLUME IF NOT EXISTS main.default.lakebridge_input;
```

手元の `input` をアップロード:

```bash
databricks fs cp --recursive ./input \
  dbfs:/Volumes/main/default/lakebridge_input/synapse
```

> Volume 名 / catalog / schema は自分の環境に合わせる。

### 3. Switch Job を起動

Databricks Workspace UI を開き、**Workflows → Jobs** で `Switch_...` を探す。`Run now with different parameters` から以下を指定:

| パラメータ | 値の例 |
|---|---|
| `input_dir` | `/Volumes/main/default/lakebridge_input/synapse` |
| `output_dir` | `/Volumes/main/default/lakebridge_output/synapse` |
| `source_tech` | `tsql` (または `synapse`) |
| `foundation_model` | `databricks-claude-sonnet-4` (ワークスペース既定のもの) |
| `concurrency` | `4` 程度 |

実行し、完了まで 3〜5 分待つ (ファイル数 × LLM 呼び出しのため、DDL + ストアド 7 本で数分)。

### 4. 生成物を確認

Workspace UI の `output_dir` 配下に変換後 SQL + コメントが生成されている。

- 特に `mssql_example2_stored_procedure.sql`: 動的 SQL / TRY-CATCH / sp_executesql が**意味的に等価な Databricks SQL + Python** で再構築されているかを観察
- 行単位コメントで「元の何行目の何を変換したか」が入っているのが Switch の特徴

### 学習ポイント

- **Switch の強み**: LLM が構文の意図を読んで書き直すため、ルールベースでは詰まる複雑ストアドでも 1 発変換を狙える
- **Switch の弱み**: LLM 呼び出しコスト、非決定性 (再実行で微妙に差分)、レビュー必須
- **使い分けの勘所**:
  - Analyzer レポートの `llm_support_needed = true` のファイル
  - DDL や定型 SQL はルールベース、複雑ストアドだけ Switch に回す
- Switch Job のパラメータで `custom_instructions` を渡すとスタイル統一もできる (応用)

---

## 3 種 Converter 比較まとめ

3 つの出力を並べて見ると:

| 観点 | BladeBridge | Morpheus | Switch |
|---|---|---|---|
| DDL 5 本 | 十分変換 | 十分変換 | 変換できるがオーバースペック |
| ストアド example1 | 大半 OK | 大半 OK | OK + 意図コメント |
| ストアド example2 (複雑) | 部分変換 | 部分変換 | **フル変換を狙える** |
| 決定性 | 高 | 高 | 中 (再実行で差分) |
| コスト | 低 | 低 | 中 (LLM 呼出) |

これが**使い分けの腹落ちポイント**。

## 次

[reconcile/](../reconcile/) で移行前後の差分検証を試す。
