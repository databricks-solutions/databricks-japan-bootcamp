# 01c. Converter: Morpheus (Synapse)

Morpheus は Databricks 純正 (Databricks Labs) のルールベーストランスパイラで、**mssql / snowflake / synapse の 3 方言に特化**。BladeBridge より対応 dialect は狭いが、純正ゆえに追従速度が速く、Synapse → Databricks の定番ペアでは品質が期待できる。

## 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect synapse \
  --input-source ./input \
  --output-folder ./out/morpheus
```

`Select the transpiler:` プロンプトで **Morpheus** を選ぶ。

> 非インタラクティブ時:
> `--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml`

## 生成物の確認

```
out/morpheus/
├── ddl/...
└── stored_procs/...
```

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
- BladeBridge は **広いカバレッジと歴史** があり、DataStage / Informatica / Teradata のような Morpheus 非対応の dialect で効く
- 同じ Synapse でも、**プロジェクトによってどちらを選ぶかは品質を見てから決める**のが実務的。今回のように両方走らせて diff を取るのが最速

## 次

[01d: Converter - Switch](01d-converter-switch.md) へ。複雑ストアドに LLM を充てる。
