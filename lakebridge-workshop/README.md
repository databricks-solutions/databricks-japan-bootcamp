# Lakebridge Workshop

Databricks Labs [Lakebridge](https://databrickslabs.github.io/lakebridge/) を実際に動かして、データウェアハウス / ETL システムから Databricks への移行を体験するハンズオンです。

## ゴール

Lakebridge の主要機能 (Analyzer / Transpile / Reconcile) を手を動かして理解し、自組織での移行案件に適用できる状態になる。

## シナリオ一覧

| ディレクトリ | 内容 |
|---|---|
| [synapse/](synapse/) | Azure Synapse Analytics (Dedicated SQL Pool) の T-SQL コードを Analyzer + 3 種 Transpiler (BladeBridge / Morpheus / Switch) で変換、特徴を比較 |
| [reconcile/](reconcile/) | 移行前後のテーブル差分検証 (Databricks 内のテーブル同士、ソースシステム不要) |
| [datastage/](datastage/) | IBM DataStage ジョブの XML エクスポートを Analyzer + BladeBridge で PySpark Notebook に変換 |

推奨順序は上表の通り (Synapse → Reconcile → DataStage)。ただし各シナリオは独立しているので、興味のあるものから試しても OK。

## 前提セットアップ

ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

### Databricks ワークスペース要件

- Unity Catalog 有効化
- Serverless SQL Warehouse が使える
- Foundation Model API (Claude Sonnet 系) の `Can Query` 権限 (Switch で利用)
- Unity Catalog の catalog / schema / volume (Switch で利用)
  - **既存リソースを使う場合**: `USE CATALOG` / `USE SCHEMA` / `CREATE TABLE` / `READ VOLUME` / `WRITE VOLUME`
  - **新規作成する場合**: catalog / schema / volume の作成権限
  - 既定値: catalog = `lakebridge`, schema = `switch`, volume = `switch_volume`

### 1. ローカル CLI インストール

#### 1.1 Databricks CLI (v0.250+)

```bash
# macOS / Linux
brew tap databricks/tap
brew install databricks

# 既にインストール済ならアップデート
brew upgrade databricks
```

Windows は公式ドキュメント参照: https://docs.databricks.com/aws/en/dev-tools/cli/install

バージョン確認:

```bash
databricks --version
```

`0.250.0` 以上の数字が返れば OK。

#### 1.2 Databricks プロファイル設定

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile DEFAULT
```

ブラウザが開くので OAuth でログイン。プロファイル名は任意。以降のコマンドで `--profile` を省略した場合 `DEFAULT` が使われる。

疎通確認:

```bash
databricks current-user me --profile DEFAULT
```

自分のユーザー情報が JSON で返れば OK。

### 2. Lakebridge インストール

```bash
databricks labs install lakebridge
```

完了後、バージョン確認:

```bash
databricks labs lakebridge --version
```

バージョン文字列 (例: `0.10.x`) が返れば OK。

### 3. Transpiler プラグインのインストール

Lakebridge の Transpiler 3 種 (BladeBridge / Morpheus / Switch) をまとめてインストールする。Switch は LLM ベースの pluggable transpiler で、**`--include-llm-transpiler true` フラグを付けないとインストールされない**。

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile DEFAULT
```

途中で選択肢が出る:

- **Select the source technology**: `tsql` などは後で `transpile` 時に指定するので、ここはどれを選んでも OK
- **Select the transpiler**: **`All`** を選んで BladeBridge / Morpheus をまとめて入れる (Switch は `--include-llm-transpiler true` 側で入る)

インストール完了後、揃っていることを確認する。

```bash
databricks labs lakebridge describe-transpile
```

出力に以下がすべて含まれていれば OK:

- `name: Bladebridge` (対応 dialect に `synapse`, `datastage` などが並ぶ)
- `name: Morpheus` (対応 dialect に `mssql`, `snowflake`, `synapse`)
- `name: Switch` (LLM ベース、任意 dialect に対応)

### 4. Reconcile 設定

```bash
databricks labs lakebridge configure-reconcile
```

- **Data Source**: `Databricks`
- **Report Type**: `all`
- その他はデフォルトで進める

初回実行時に Lakebridge 用の catalog/schema (`remorph_reconcile` 既定) とメタデータテーブルが自動作成される。

### 5. リポジトリを clone

```bash
git clone https://github.com/databricks-solutions/databricks-japan-bootcamp.git
cd databricks-japan-bootcamp/lakebridge-workshop
```

準備完了。あとは好きなシナリオから進める。

## トラブルシュート

### `databricks labs lakebridge describe-transpile` に Morpheus / Switch が出ない

`install-transpile` 実行時に `All` を選んでいない、もしくは `--include-llm-transpiler true` を付けていない可能性。再度:

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile DEFAULT
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

`configure-reconcile` で指定した metadata catalog/schema を `databricks labs lakebridge configure-reconcile --profile DEFAULT` で再確認。既定は `remorph_reconcile`。

## 参考

- Lakebridge 公式ドキュメント: https://databrickslabs.github.io/lakebridge/
- Switch (Lakebridge の pluggable transpiler): https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/
- `databricks labs lakebridge describe-transpile` で利用可能な transpiler と dialect を常に確認できる
