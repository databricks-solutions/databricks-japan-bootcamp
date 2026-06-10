# Lakebridge Workshop

Databricks Labs [Lakebridge](https://databrickslabs.github.io/lakebridge/) を実際に動かして、データウェアハウス / ETL システムから Databricks への移行を体験するハンズオン。

## ゴール

Lakebridge の主要機能 (Analyzer / Transpile / Reconcile) を手を動かして理解し、自組織での移行案件に適用できる状態になる。

## シナリオ一覧

| ディレクトリ | 内容 |
|---|---|
| [datastage/](datastage/) | IBM DataStage ジョブの XML エクスポートを Analyzer + BladeBridge で PySpark Notebook に変換 |
| [reconcile/](reconcile/) | 移行前後のテーブル差分検証 (Databricks 内のテーブル同士、ソースシステム不要) |
| [synapse/](synapse/) | Azure Synapse Analytics (Dedicated SQL Pool) の T-SQL コードを Analyzer + 3 種 Converter (BladeBridge / Morpheus / Switch) で変換、特徴を比較 |

推奨順序は **Synapse → Reconcile → DataStage** だが、各シナリオは独立しているので、興味のあるものから着手しても構わない。シナリオは今後も追加していく予定。

## セットアップ

各シナリオを始める前に、共通セットアップ ([SETUP.md](SETUP.md)) を完了させる (所要 10〜15 分。Databricks CLI、Lakebridge、Converter のインストール)。reconcile シナリオのみ、追加のシナリオ固有設定が [reconcile/README.md](reconcile/README.md) の冒頭にある。

## 参考

- Lakebridge 公式ドキュメント: https://databrickslabs.github.io/lakebridge/
- Switch (Lakebridge の pluggable transpiler): https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/
- `databricks labs lakebridge describe-transpile` で利用可能な Converter と対応ソースを常に確認できる (Switch は除く)
