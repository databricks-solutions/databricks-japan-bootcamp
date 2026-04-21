# _reference_output (DataStage シナリオ)

DataStage シナリオを実行した際の **参考出力例**。自分で `databricks labs lakebridge analyze` / `transpile` を回した結果 (`../out/` に生成される) と、ここを見比べて差分を確認するのに使う。

## 構成

| パス | 何の出力か | 生成コマンド |
|---|---|---|
| `datastage-report.xlsx` | Analyzer レポート (多数のシート) | `databricks labs lakebridge analyze ...` |
| `bladebridge/SAMPLE_JOB.py` | BladeBridge での Transpile 結果 (PySpark Notebook) | `databricks labs lakebridge transpile --source-dialect datastage --target-technology PYSPARK ...` |
| `bladebridge/databricks_conversion_supplements.py` | BladeBridge が自動生成する共通ユーティリティ (column renaming 等) | 同上 |

## 注意

- これらは**スナップショット**。Lakebridge / BladeBridge のバージョンアップで出力は変わるため、厳密な等価性は期待しない
- Analyzer のシート数やレイアウトは BladeBridge のバージョンで前後する
