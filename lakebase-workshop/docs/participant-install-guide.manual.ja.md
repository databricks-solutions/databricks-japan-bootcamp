# Lakebaseワークショップ Appインストールガイド（手動接続版）

この構成は、Databricks AppsのDatabase resourceを利用できない環境向けの
フォールバック版です。従来の2変数方式と個別`PG*`方式をサポートします。

このワークショップでいう「チケット」は、サポート問い合わせ、作業依頼、脆弱性アイテム等を管理するレコードです。service principal Client IDを本ガイドではApp IDと呼びます。

## 初回デプロイ

1. `lakebase-workshop`のsource folderを別に複製し、複製先の`app.yaml`を
   `app.manual.yaml`の内容で置き換えます。
2. 置き換えた`app.yaml`が直下にあるfolderをWorkspaceへアップロードします。
3. Databricks Appsで新しいAppを作成します。
4. **Deploy**でアップロードしたfolderを選択します。
5. Appを開き、黄色の`デモモード`と`[DEMO]`で始まる3件を確認します。
6. App詳細画面でservice principalのClient ID（App ID）を確認します。

## branchとrole

1. 講師から割り当てられたmaster projectの`production`から自分のbranchを作成し、Auto-deleteを`After 1 day`に設定します。
2. 自分のbranchで**Roles & Databases**→**Add role**を選びます。
3. Appのservice principalを選択します。
4. superuser権限のオプションを有効にしてroleを作成します。

roleは必ず自分のbranchに作成し、`production`には作成しません。

## 手動接続

Apps UIのEnvironmentまたは`app.yaml`で次を設定し、再デプロイします。

```yaml
env:
  - name: LAKEBASE_CONNECTION_STRING
    value: "<自分のbranchのConnection detailsで取得したCopy snippet>"
  - name: ENDPOINT_NAME
    value: "projects/<master project>/branches/<自分のbranch>/endpoints/primary"
```

`PGUSER`はDatabricks Appsの`DATABRICKS_CLIENT_ID`を自動利用します。
接続値は`notebooks/participant_connect_helper.py`でも確認できます。

再デプロイ後、緑の接続バッジ、`databricks_postgres`、自分のbranch、
Lakebase用の5件を確認します。

## 成果を確認する

1. チケットを1件更新し、ticket IDを控えます。
2. 自分のbranchの`tickets`で更新を確認します。
3. `production`の同じticket IDが元のままであることを確認します。
4. branch名、ticket ID、`production`無傷を講師指定のフォームまたはチャットへ記録します。

## 互換設定

`LAKEBASE_CONNECTION_STRING`の代わりに、`PGHOST`、`PGDATABASE`、
`PGPORT`、`PGSSLMODE`、`PGUSER`を個別設定する方式も利用できます。

トラブルの切り分け:

| 症状 | 確認点 | 復旧操作 |
|---|---|---|
| `password authentication failed` | App role | App IDのroleを自分のbranchへ作成 |
| `permission denied for table tickets` | superuserオプション | roleを修正または再作成 |
| 黄色のデモモードのまま | `LAKEBASE_CONNECTION_STRING` | 値を設定して再Deploy |

## 次の一歩

講師へPoC、個別アーキテクチャ相談、次回ハンズオンのいずれを希望するか伝えてください。
