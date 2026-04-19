# シナリオ 1: Synapse / T-SQL マイグレーション

Azure Synapse Analytics (Dedicated SQL Pool) から Databricks への移行を想定し、**Analyzer** で規模感を掴んだ上で、**3 種類の Converter** (BladeBridge / Morpheus / Switch) で同じインプットを変換し、それぞれの強みと使い分けを体感する。

## 進め方

| 手順 | 手順書 | 所要目安 |
|---|---|---|
| 1a | [Analyzer 実行](01a-analyzer.md) | 13 分 |
| 1b | [Converter: BladeBridge](01b-converter-bladebridge.md) | 10 分 |
| 1c | [Converter: Morpheus](01c-converter-morpheus.md) | 10 分 |
| 1d | [Converter: Switch](01d-converter-switch.md) | 17 分 |

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

3 つ走らせた後 (または AMA) で「どういう入力を誰に投げるか」を議論する。
