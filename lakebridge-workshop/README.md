# Lakebridge Workshop

Databricks Labs [Lakebridge](https://databrickslabs.github.io/lakebridge/) を実際に動かして、データウェアハウス / ETL システムから Databricks への移行を体験するハンズオンです。

## ゴール

Lakebridge の主要機能 (Analyzer / Transpile / Reconcile) を手を動かして理解し、自組織での移行案件に適用できる状態になる。

## シナリオ一覧

| ディレクトリ | 内容 |
|---|---|
| [datastage/](datastage/) | IBM DataStage ジョブの XML エクスポートを Analyzer + BladeBridge で PySpark Notebook に変換 |
| [reconcile/](reconcile/) | 移行前後のテーブル差分検証 (Databricks 内のテーブル同士、ソースシステム不要) |
| [synapse/](synapse/) | Azure Synapse Analytics (Dedicated SQL Pool) の T-SQL コードを Analyzer + 3 種 Transpiler (BladeBridge / Morpheus / Switch) で変換、特徴を比較 |

推奨順序は **Synapse → Reconcile → DataStage**。各シナリオは独立しているため、必要に応じて順序を変えて進めても OK。

## 前提セットアップ

ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

### Databricks ワークスペース要件

- **Unity Catalog** 有効化 (全シナリオ)
- **Serverless SQL Warehouse** が使える (Reconcile で利用)
- **Foundation Model API** (Claude Sonnet 系) の `Can Query` 権限 (Switch で利用)
- **Unity Catalog の catalog / schema / volume** (Switch で利用)
  - 既存リソースを使う場合: `USE CATALOG` / `USE SCHEMA` / `CREATE TABLE` / `READ VOLUME` / `WRITE VOLUME`
  - 新規作成する場合: catalog / schema / volume の作成権限
  - 既定値: catalog = `lakebridge`, schema = `switch`, volume = `switch_volume`

### 1. ローカル CLI インストール

Databricks CLI をインストールする。OS 別の手順は [公式ドキュメント (日本語)](https://docs.databricks.com/aws/ja/dev-tools/cli/install) を参照。

インストール完了後、バージョン確認:

```bash
databricks --version
```

`v0.250.0` 以上の数字が返れば OK。

### 2. Databricks プロファイル設定

ワークスペースのホスト URL は Cloud によって形式が違う:

- AWS: `https://<workspace-id>.cloud.databricks.com`
- Azure: `https://adb-<workspace-id>.<suffix>.azuredatabricks.net`
- GCP: `https://<workspace-id>.gcp.databricks.com`

実際の値は Databricks コンソールで確認。以下、自分のプロファイル名を `<your-profile>` と置く (任意の名前)。

```bash
databricks auth login --host <your-workspace-host> --profile <your-profile>
```

ブラウザが開くので OAuth でログイン。以降のコマンドはこの `<your-profile>` を指定して実行する。

疎通確認:

```bash
databricks current-user me --profile <your-profile>
```

自分のユーザー情報が JSON で返れば OK。

#### `cluster_id` / `warehouse_id` の追記

Lakebridge はプロファイルに `cluster_id` と `warehouse_id` が設定されていることを期待する:

- `cluster_id`: Lakebridge の CLI コマンド実行で利用 (Lakebridge 公式 Docs 上の要件)
- `warehouse_id`: `transpile` の出力検証や `reconcile` のジョブ実行で利用

ID を取得する (Databricks コンソール UI から見るか、CLI で一覧):

```bash
# Cluster ID (All-purpose クラスタを想定)
databricks clusters list --profile <your-profile>

# Warehouse ID (Serverless SQL Warehouse を推奨)
databricks warehouses list --profile <your-profile>
```

`~/.databrickscfg` を開き、`[<your-profile>]` セクションに 2 行追記する (auth 関連の行は `databricks auth login` が既に書いているので維持):

```ini
[<your-profile>]
host         = https://<your-workspace-host>
...
cluster_id   = 0123-456789-abcdef01
warehouse_id = abc123def456ghi7
```

### 3. Lakebridge インストール

```bash
databricks labs install lakebridge --profile <your-profile>
```

完了後、バージョン確認:

```bash
databricks labs lakebridge --version
```

バージョン文字列 (例: `0.10.x`) が返れば OK。

### 4. Transpiler プラグインのインストール

Lakebridge の Transpiler 3 種 (BladeBridge / Morpheus / Switch) をまとめてインストールする。Switch は LLM ベースの pluggable transpiler で、**`--include-llm-transpiler true` フラグを付けないとインストールされない**。

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile <your-profile>
```

インタラクティブにいくつか設定を聞かれる (既定の source technology など)。ここで答えた値は以降の `transpile` コマンドの既定値になる。迷ったら既定のまま進めても、後で CLI オプションで上書きできる。

インストール完了後、揃っていることを確認する。

```bash
databricks labs lakebridge describe-transpile
```

出力に以下がすべて含まれていれば OK:

- `name: Bladebridge` (対応 dialect に `synapse`, `datastage` などが並ぶ)
- `name: Morpheus` (対応 dialect に `mssql`, `snowflake`, `synapse`)
- `name: Switch` (LLM ベース、任意 dialect に対応)

### 5. Reconcile 設定

```bash
databricks labs lakebridge configure-reconcile --profile <your-profile>
```

- **Data Source**: `Databricks`
- **Report Type**: `all`
- その他はデフォルトで進める

初回実行時に Lakebridge 用の catalog/schema (`remorph_reconcile` 既定) とメタデータテーブルが自動作成される。

### 6. リポジトリを clone

```bash
git clone https://github.com/databricks-solutions/databricks-japan-bootcamp.git
cd databricks-japan-bootcamp/lakebridge-workshop
```

準備完了。あとは好きなシナリオから進める。

## トラブルシュート

### `databricks labs lakebridge describe-transpile` に Switch が出ない

`install-transpile` 実行時に `--include-llm-transpiler true` を付けていないと Switch は入らない。以下を実行して再インストール:

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile <your-profile>
```

### `transpile` コマンドが `EOFError` で落ちる

非インタラクティブ環境 (CI など) で `Select the transpiler:` プロンプトが待てずに落ちる。明示的に config-path を指定する。

```bash
# BladeBridge
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml

# Morpheus
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml
```

### Switch の `llm-transpile` が Foundation Model で失敗する

ワークスペースで Foundation Model エンドポイント (例: `databricks-claude-sonnet-4-5`) への `Can Query` 権限を確認。権限が無ければワークスペース管理者に付与依頼。

### Reconcile のレポートテーブルが見つからない

`configure-reconcile` で指定した metadata catalog/schema を以下で再確認。既定は `remorph_reconcile`。

```bash
databricks labs lakebridge configure-reconcile --profile <your-profile>
```

## 参考

- Lakebridge 公式ドキュメント: https://databrickslabs.github.io/lakebridge/
- Switch (Lakebridge の pluggable transpiler): https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/
- `databricks labs lakebridge describe-transpile` で利用可能な transpiler と dialect を常に確認できる
