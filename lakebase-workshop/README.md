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

## 講師向け準備と片付け

ワークショップ環境はDatabricks workspace上のnotebookだけで準備できます。ローカルの
Databricks CLI、jq、psqlは不要です。

1. `notebooks/facilitator_setup.py`と`notebooks/facilitator_cleanup.py`をworkspaceへ
   importします。
2. `facilitator_setup`を一度Run allし、表示されたwidgetへ参加者数、project接頭辞、
   参加者グループ、権限モードを入力します。初回のRun allは確認だけで、環境を変更しません。
3. `5. 実行確認`を`環境構築を実行`へ変更して、もう一度Run allします。参加者8名ごとに
   master projectを作成し、schemaとsample dataの投入、`production` branchのprotected化、
   参加者グループへの権限付与を行います。
4. 最後に出力される参加者割り当て表を参加者へ配布します。開始前に、代表参加者で
   branchを作成できることを確認してください。
5. 終了後は`facilitator_cleanup`を実行します。初回は削除対象の一覧だけを表示し、
   `2. 削除確認`へproject接頭辞を再入力した場合だけprojectを完全に削除します。
   削除は取り消せません。

1つのprojectでunarchivedのbranchは最大10本です。setup notebookは講師確認用を含めて
1 projectあたり9本以内に収まるよう、参加者を8名ずつ分割します。

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
- `notebooks/facilitator_setup.py`: 講師用の環境作成notebook
- `notebooks/facilitator_cleanup.py`: 講師用の環境削除notebook
- `notebooks/participant_connect_helper.py`: 手動接続用の診断helper
- `docs/`: 参加者向け日英インストールガイド
- `tests/`: unit test

ワークショップ設計資料とworkspace固有のdeployment scriptは、この公開版に含まれません。

## 第三者ライブラリ

このアプリは[Psycopg](https://github.com/psycopg/psycopg) 3.3.4を使用します。
licenseはLGPL-3.0-onlyです。依存関係は`pyproject.toml`と`uv.lock`で固定しています。

## Support and License

本コンテンツはDatabricksの公式support対象ではありません。不具合はこの
repositoryのGitHub Issueへ報告してください。利用条件はrepository rootの
[LICENSE.md](../LICENSE.md)と[NOTICE.md](../NOTICE.md)を参照してください。
