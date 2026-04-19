# 前提セットアップ

各シナリオを動かす前に、ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

## Databricks ワークスペース要件

- Unity Catalog 有効化
- Serverless SQL Warehouse が使える
- Foundation Model API (Claude Sonnet) の `Can Query` 権限 (Switch で利用)
- 自分がワークスペースオーナー権限 or `CREATE CATALOG` を持つ

## 1. ローカル CLI インストール

### 1.1 Databricks CLI (v0.250+)

```bash
# macOS / Linux
brew tap databricks/tap
brew install databricks

# 既にインストール済ならアップデート
brew upgrade databricks

# バージョン確認 (0.250+ 推奨)
databricks --version
```

Windows は公式ドキュメント参照: https://docs.databricks.com/aws/en/dev-tools/cli/install

### 1.2 Databricks プロファイル設定

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile DEFAULT
```

ブラウザが開くので OAuth でログイン。プロファイル名は任意。以降のコマンドで `--profile` を省略した場合 `DEFAULT` が使われる。

```bash
# 疎通確認
databricks current-user me --profile DEFAULT
```

## 2. Lakebridge インストール

```bash
databricks labs install lakebridge

# バージョン確認
databricks labs lakebridge --version
```

## 3. Transpiler プラグインのインストール

Synapse シナリオで BladeBridge / Morpheus / Switch の 3 種すべてを使うため、まとめてインストールする。

```bash
databricks labs lakebridge install-transpile --profile DEFAULT
```

途中で選択肢が出る:

- **Select the source technology**: `tsql` などは後で `transpile` 時に指定するので、ここはどれを選んでも OK
- **Select the transpiler**: **`All`** を選んで BladeBridge / Morpheus / Switch をまとめて入れる

インストール完了後、揃っていることを確認する。

```bash
databricks labs lakebridge describe-transpile
```

出力に以下が含まれていれば OK:

- `name: Bladebridge` (対応 dialect に `synapse`, `datastage` などが並ぶ)
- `name: Morpheus` (対応 dialect に `mssql`, `snowflake`, `synapse`)
- `name: Switch` (LLM ベース、任意 dialect に対応)

## 4. Reconcile 設定

[reconcile/](reconcile/) シナリオで使う。

```bash
databricks labs lakebridge configure-reconcile
```

- **Data Source**: `Databricks`
- **Report Type**: `all`
- その他はデフォルトで進める

初回実行時に Lakebridge 用の catalog/schema (`remorph_reconcile` 既定) とメタデータテーブルが自動作成される。

## 5. リポジトリを clone

```bash
git clone https://github.com/databricks-solutions/databricks-japan-bootcamp.git
cd databricks-japan-bootcamp/lakebridge-workshop
```

準備完了。[README](README.md) に戻って好きなシナリオから進める。
