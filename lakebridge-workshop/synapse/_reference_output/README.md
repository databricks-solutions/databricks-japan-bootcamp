# _reference_output (Synapse シナリオ)

Synapse シナリオを実行した際の **参考出力例**。自分で `databricks labs lakebridge analyze` / `transpile` を回した結果 (`../out/` に生成される) と、ここを見比べて差分を確認するのに使う。

## 構成

| パス | 何の出力か | 生成コマンド |
|---|---|---|
| `synapse-report.xlsx` | Analyzer レポート (13 シート) | `databricks labs lakebridge analyze ...` |
| `bladebridge/ddl/*.sql`, `bladebridge/stored_procs/*.sql` | BladeBridge での Transpile 結果 | `databricks labs lakebridge transpile --source-dialect synapse ...` で **Bladebridge** を選択 |
| `morpheus/ddl/*.sql`, `morpheus/stored_procs/*.sql` | Morpheus での Transpile 結果 | `databricks labs lakebridge transpile --source-dialect synapse ...` で **Morpheus** を選択 |
| `switch/ddl/*.py`, `switch/stored_procs/*.py` | Switch (LLM ベース) での Transpile 結果 (Python Notebook) | `databricks labs lakebridge llm-transpile --source-dialect synapse ...` |

## 注意

- これらは**スナップショット**。Lakebridge / 各 Transpiler のバージョンアップで出力は変わるため、厳密な等価性は期待しない
- **Switch は Workspace 上に Python Notebook を出力**する。ここに置いてあるのは、Workspace から `databricks workspace export-dir` 等でローカルに落としたコピー (参照しやすさのため)。実際のワークショップ実行時は Workspace 上で開いて確認する (`synapse/README.md` の Switch セクション参照)
- BladeBridge は `--skip-validation false` (既定) で実行した結果。Validator で弾かれたファイルは `-- Exception Start -- ... -- Exception End --` ブロックでコメント化されている
