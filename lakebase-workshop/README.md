# Lakebase Workshop Ticket App

Databricks AppsからLakebase Postgresへ接続し、branchごとに分離されたデータを
更新するワークショップ用のサンプルアプリです。参加者はチケットのstatus、owner、
commentを更新し、自分のbranchだけに変更が反映されることを確認します。

## 参加者向けガイド

- [日本語インストールガイド](docs/participant-install-guide.ja.md)
- [English installation guide](docs/participant-install-guide.en.md)
- [日本語手動接続ガイド](docs/participant-install-guide.manual.ja.md)
- [English manual connection guide](docs/participant-install-guide.manual.en.md)

標準手順ではDatabricks AppsのDatabase resourceを使用します。Database resourceを
利用できない場合だけ、手動接続ガイドと`app.manual.yaml`を使用してください。

## ローカルデモ

ローカルではSQLite demo modeで起動します。Lakebase接続やDatabricks credentialは
不要です。

```bash
uv sync --frozen
uv run --frozen python app.py
```

起動後、`http://localhost:8000`を開きます。`[DEMO]`で始まる3件のチケットが
表示されれば正常です。

## Unit Test

```bash
uv run --frozen python -m unittest discover -s tests -v
```

## ファイル構成

- `app.py`: application server、API、Lakebase接続処理
- `app.yaml`: Database resource方式のDatabricks Apps設定
- `app.manual.yaml`: 手動接続方式のフォールバック設定
- `requirements.txt`: Databricks Appsが導入するPython runtime依存関係
- `pyproject.toml`、`uv.lock`: ローカル検証用に固定したPython依存関係
- `static/`: browser UI
- `sql/`: PostgreSQL／SQLiteのschemaとsample data
- `notebooks/participant_connect_helper.py`: 手動接続用の診断helper
- `docs/`: 参加者向け日英インストールガイド
- `tests/`: unit test

講師用の環境作成・削除処理、ワークショップ設計資料、workspace固有のdeployment
scriptはこの公開版に含まれません。

## 第三者ライブラリ

このアプリは[Psycopg](https://github.com/psycopg/psycopg) 3.3.4を使用します。
licenseはLGPL-3.0-onlyです。依存関係は`pyproject.toml`と`uv.lock`で固定しています。

## Support and License

本コンテンツはDatabricksの公式support対象ではありません。不具合はこの
repositoryのGitHub Issueへ報告してください。利用条件はrepository rootの
[LICENSE.md](../LICENSE.md)と[NOTICE.md](../NOTICE.md)を参照してください。
