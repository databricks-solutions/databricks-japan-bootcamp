# Lakebridge Workshop Agent Guide

このディレクトリ配下は、Lakebridge の日本語ハンズオン教材です。

## 基本方針

- 変更前に `README.md`、`SETUP.md`、対象ディレクトリの `README.md` を読む。
- 教材と説明は日本語で記述する。
- 各ハンズオンは単独で実行できる状態を保つ。
- 顧客名、Databricks プロファイル名、Workspace URL / ID、Warehouse ID、ユーザー名、ローカル絶対パス、認証情報をコミットしない。

## ディレクトリ規約

- `<handson>/input/`: 再現可能な入力例。Git 管理する。
- `<handson>/out/`: 学習者の生成物。Git 管理しない。
- `<handson>/_reference_output/`: 参考出力。実生成物と比較し、使用したバージョンを対象 README に記載してから Git 管理する。
- Python の `__pycache__/` など、実行時に生成されるファイルを追加しない。

## ドキュメント

- 共通の作業ルールはこのファイルに置く。
- ハンズオン固有の手順や制約は、対象ディレクトリの `README.md` に置く。
- ハンズオンの一覧をこのファイルや `CLAUDE.md` に複製しない。
- トラブルシュートは **問題 / 原因 / 対処** の順で記述する。

## 検証

- JSON: `python3 -m json.tool <file>`
- Python: `PYTHONPYCACHEPREFIX=/tmp/lakebridge-pycache python3 -m py_compile <file>`
- Markdown のローカルリンクが存在することを確認する。
- `git diff --check` を実行する。
- Databricks 接続を利用できる場合は、対象 README の手順を最初から実行する。
