# Lakebase ワークショップ App インストールガイド

この構成はDatabricks AppsのAdd resource方式で、自分のLakebase branchへ
接続する正規版です。

このワークショップでいう「チケット」は、サポート問い合わせ、作業依頼、脆弱性アイテム等を管理するレコードです。App詳細画面に表示されるservice principal Client IDを、本ガイドではApp IDと呼びます。

## この手順に含まれること / 含まれないこと

- Databricks Appを作成する
- 講師が用意した`production`（master）から自分のbranchを作成する（テーブル・データはコピーされる）
- 自分のブランチにApp用のロールを作成する
- AppsのResourcesからDatabaseを追加する
- AppをデプロイしてLakebaseへ接続する
- チケットを更新し、自分のbranchだけに反映されることを確認する

接続文字列や`ENDPOINT_NAME`の手入力は不要です。

## Databricks UI からインストールする

1. Databricks workspace を開きます。
2. このリポジトリをdownloadまたはcloneし、`lakebase-workshop`フォルダを開きます。
3. Databricksの**Workspace**を開き、`lakebase-workshop`の中身を次のような
   workspace folderへアップロードします。

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

   このfolderの直下に`app.yaml`、`app.py`、`pyproject.toml`、`static/`が
   見える状態にしてください。

4. 画面右上のアプリスイッチャーから **Databricks アプリ（Apps）** を開きます。
5. 新しいAppを作成します。この時点ではまだデプロイしません。
6. App詳細画面でservice principalのClient ID（App ID）を確認します。後でroleを作成するときに同じAppを選択します。

## productionから自分のbranchを作成する

1. 画面右上から**Lakebase Postgres**を開きます。
2. 割り当てられたmaster projectを開きます。
3. `production` branchから新しいbranchを作成します。
4. branch名に自分の名前を入力し、Auto-deleteを`After 1 day`にします。
5. branchとendpointが作成されるまで待ちます。

## Appのroleを自分のbranchへ作成する

1. 画面右上から**Lakebase Postgres**を開きます。
2. 作成した自分のbranchを開きます。
3. **Roles & Databases**→**Add role**を選びます。
4. Service principalで手順6のAppを選択します。
5. **superuser権限のオプションを有効にして**roleを作成します。

roleは必ず自分のbranchに作成し、`production`には作成しません。

## AppsからDatabase resourceを追加する

1. 作成したAppへ戻り、**Resources**→**Add resource**を選びます。
2. Resource typeで**Database**を選びます。
3. 次の値を設定します。

   | 項目 | 値 |
   |---|---|
   | Resource key | `lakebase-demo` |
   | Project | 講師から割り当てられたmaster project |
   | Branch | 自分のbranch |
   | Database | `databricks_postgres` |
   | Permission | `Can connect and create` |

4. Resourceを保存します。

`lakebase-demo`は`app.yaml`の`valueFrom`と一致させる固定値です。別のkeyを使うと
デプロイ後に`ENDPOINT_NAME`を解決できません。

## Appをデプロイする

1. App詳細画面で**Deploy**をクリックします。
2. Source folderの選択画面で、アップロードしたworkspace folderを選びます。

   例:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

   ここで選ぶ folder は、開いたときに `app.yaml` が直下にある folder です。
   `static/`の内側ではありません。

3. **Select**→**Deploy**をクリックします。
4. Appを開き、接続バッジが緑色で次を表示することを確認します。
   - `Lakebase 接続済み`
   - database: `databricks_postgres`
   - branch: 自分のbranch
   - `Apps resource`
5. Lakebase用の5件のチケットが表示されることを確認します。

テーブルとデータは`production`からブランチにコピー済みのため、`INIT_DB`は
**設定しません**。`PGDATABASE=databricks_postgres`はLakebase project既定の
database です。このワークショップでは参加者が database を作成する必要はありません。

## 成果を確認する

1. チケットを1件選び、ticket IDを控えます。
2. statusを変更し、ownerを自分の名前にして保存します。
3. 画面右上から**Lakebase Postgres**→自分のbranch→**Tables**→`tickets`を開きます。
4. 控えたticket IDのstatus、owner、updated_atが変わっていることを確認します。
5. 同じmaster projectの`production`→**Tables**→`tickets`を開きます。
6. 同じticket IDが元のままであることを確認します。

完了時に次の3点を講師指定のフォームまたはチャットへ記録します。

- 自分のbranch名
- 更新したticket ID
- `production`無傷: 確認済み

## フォールバック: 手動接続方式

Database resourceを選択できない環境では、source folderを別に複製して
`app.manual.yaml`を`app.yaml`として使用します。この構成はSQLite demo modeで
初回起動でき、従来どおり次の2変数で接続できます。完全な手順は
[手動接続版ガイド](participant-install-guide.manual.ja.md)を参照してください。

```yaml
env:
  - name: LAKEBASE_CONNECTION_STRING
    value: "<Connection detailsのCopy snippet>"
  - name: ENDPOINT_NAME
    value: "projects/<master project>/branches/<自分のbranch>/endpoints/primary"
```

`PGUSER`は`DATABRICKS_CLIENT_ID`を自動利用します。個別の`PG*`設定も互換性のため
利用できます。接続値の確認には`notebooks/participant_connect_helper`を使用します。

トラブルの切り分け:

| 症状 | 確認点 | 復旧操作 |
|---|---|---|
| 黄色のデモモードのまま | Database resourceとDeploy状態 | resource追加後に再Deploy |
| `password authentication failed` | 自分のbranchにApp roleがあるか | App IDのroleを作成 |
| `permission denied for table tickets` | superuserオプション | roleを修正または再作成 |
| `valueFrom: lakebase-demo`の案内 | Resource key | keyを`lakebase-demo`へ修正して再Deploy |

## 次の一歩

自分の業務へ適用したい場合は、講師へ次のいずれかを伝えてください。

1. 自分のユースケースでPoCを進めたい
2. Lakebase、Unity Catalog／Delta、DBSQLの配置を相談したい
3. 次回ハンズオンまたは中級編へ参加したい

## アプリコードを更新する

source codeを更新する場合は、Databricks AppやLakebaseは削除しません。
Workspace上のsource folderだけを入れ替えて、既存Appを再デプロイします。

1. Databricks の **Workspace** を開きます。
2. 既存の source folder を削除します。

   例:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

3. リポジトリの最新版をdownloadまたはcloneします。
4. 新しい`lakebase-workshop`の中身を同じ場所へアップロードし、folder名が
   前と同じであることを確認します。

   例:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

5. folderの直下に`app.yaml`、`app.py`、`pyproject.toml`、`static/`、`sql/`があることを確認します。
6. Databricks Apps で既存 App を開きます。
7. **Deploy** をクリックし、同じ source folder を選んで再デプロイします。

削除してよいもの:

- Workspace 上の source folder

削除しないもの:

- Databricks App
- Lakebase project / database / table
- App の環境変数

Databricks App を削除すると App service principal が変わる可能性があり、
Lakebase側のrole grantをやり直す必要が出ます。通常の更新では
App は残したまま再デプロイしてください。

## 含まれるファイル

- `app.py`: application server
- `app.yaml`: Add resource方式のDatabricks Apps config
- `app.manual.yaml`: 手動接続方式のフォールバックconfig
- `pyproject.toml`と`uv.lock`: 固定されたPython runtime依存関係
- `static/`: browser UI
- `sql/`: ワークショップ用の参考 schema / seed files
- `notebooks/participant_connect_helper.py`: 手動接続用の診断helper

公開版にはLakebaseの作成、setup、cleanup、workspace固有のdeployment scriptは
含まれていません。
