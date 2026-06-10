# lakebridge-workshop

Databricks Labs Lakebridge のハンズオン教材。各シナリオの内容・手順は README を参照。

- 全体概要: `README.md`
- 共通セットアップ (ローカル CLI 前提): `SETUP.md`。シナリオ固有のセットアップは各シナリオ README に置く (例: reconcile の `configure-reconcile`)
- シナリオ別: `synapse/README.md` / `reconcile/README.md` / `datastage/README.md`
- 英語版は [databricks-solutions/lakebridge-workshop](https://github.com/databricks-solutions/lakebridge-workshop) で独立管理 (対訳同期はしない)

## ディレクトリ規約

| ディレクトリ | 用途 | git 管理 |
|---|---|---|
| `<scenario>/input/` | ワークショップの入力データ (編集不要) | ✅ |
| `<scenario>/out/` | 学習者各自の実行結果 (各自のローカルで生成) | ❌ (`.gitignore` 除外) |
| `<scenario>/_reference_output/` | 参考までに見られる出力例 (編集者が整備) | ✅ |

`_reference_output/` は「学習者が再実行した結果と見比べる」用。ファイル構成は各 `_reference_output/README.md` を参照。

## スタイル規約

- 言語: 日本語
- トラブルシュート項目は **問題 / 原因 / 対処** の 3 段構造で書く (SETUP.md 参照)

## 参考

- Lakebridge 公式: https://databrickslabs.github.io/lakebridge/
