# Lakebridge Workshop Agent Guide

このディレクトリ配下は、Databricks Labs Lakebridge の日本語ハンズオン教材です。

## 基本方針

- 変更前に全体の `README.md`、`SETUP.md`、対象シナリオの `README.md` を読む。
- 教材と説明は日本語で記述する。
- 既存シナリオは独立して実行できる状態を保つ。
- 顧客名、Databricks プロファイル名、Workspace URL / ID、Warehouse ID、ユーザー名、ローカル絶対パス、認証情報をコミットしない。

## ディレクトリ規約

- `<scenario>/input/`: 再現可能な入力例。Git 管理する。
- `<scenario>/out/`: 学習者の生成物。Git 管理しない。
- `<scenario>/_reference_output/`: バージョンを明記した参考出力。実生成物と比較してから Git 管理する。
- Python の `__pycache__/` など、実行時に生成されるファイルを追加しない。

## coding-agent シナリオ

- 中心メッセージは「変換後 SQL を直接直さず、変換ルールを直して元入力から再生成する」。
- `out/before/` や `out/solution/` を手修正して解決しない。
- `overrides/teradata-overrides.json` の `__BLADEBRIDGE_BASE_CONFIG__` を環境固有パスへ置換しない。
- 実行用 override は `tools/prepare_overrides.py` で `out/` に生成する。
- 完成例では、標準変換が `FAIL 2`、override 適用後が `FAIL 0` になることを確認する。

## 検証

- JSON: `python3 -m json.tool <file>`
- Python: `PYTHONPYCACHEPREFIX=/tmp/lakebridge-pycache python3 -m py_compile <file>`
- Markdown のローカルリンクが存在することを確認する。
- `git diff --check` を実行する。
- Databricks 接続が利用できる場合は、対象 README の変換と SQL 構文チェックを最初から実行する。
