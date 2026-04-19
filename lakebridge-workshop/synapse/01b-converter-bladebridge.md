# 01b. Converter: BladeBridge (Synapse)

BladeBridge は Travinto Technologies 由来のルールベーストランスパイラ。**多数の source dialect** (datastage / informatica / ssis / synapse / teradata / oracle / netezza / redshift ...) に対応しており、ETL メタデータや DDL、定型 SQL の変換が得意。

## 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/bladebridge
```

`Select the transpiler:` プロンプトが出るので **Bladebridge** を選ぶ。
(Morpheus も synapse に対応しているため、synapse では候補が 2 つ出る)

> 非インタラクティブ (CI など) でプロンプトを避けたい場合:
> `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml`

## 生成物の確認

```
out/bladebridge/
├── ddl/
│   ├── 01_customers.sql
│   ├── 02_products.sql
│   ├── ...
├── stored_procs/
│   ├── mssql_example1_multi_statement_transformation.sql
│   └── mssql_example2_stored_procedure.sql
└── transpile-report.json   # or similar
```

### DDL の変換結果を観察

`out/bladebridge/ddl/01_customers.sql` を開き、元ファイルと見比べる:

- `NVARCHAR` → `STRING`、`DATETIME2` → `TIMESTAMP` など型マッピング
- `WITH (DISTRIBUTION = HASH(...), CLUSTERED COLUMNSTORE INDEX)` の扱い (Databricks には不要のため**削除 or コメント化**されるはず)
- `DEFAULT SYSUTCDATETIME()` → `DEFAULT CURRENT_TIMESTAMP()` 近辺
- `CREATE STATISTICS` は Databricks に概念がない → コメントアウト or スキップ

### ストアドの変換結果を観察

`out/bladebridge/stored_procs/mssql_example2_stored_procedure.sql` は**高確率で部分変換**になる。`sp_executesql` / 動的 SQL / `TRY/CATCH` は Databricks SQL にそのまま翻訳できない。

生成ファイル内に `-- UNSUPPORTED:` 的なコメントや、エラーレポート (`transpile-report.*`) に**変換できなかった箇所**が列挙されているはずなので、ここを見る。

### 学習ポイント

- **DDL / 定型 SQL**: ルールベースで高速・決定論的に変換できる
- **複雑ストアド**: ルールベースでは限界があり、Switch (LLM) の出番
- 案件では「DDL は BladeBridge で一気に、ストアドは Switch で個別に」という役割分担が定石

## 次

[01c: Converter - Morpheus](01c-converter-morpheus.md) へ。同じ input を Morpheus に投げて、BladeBridge との差分を見る。
