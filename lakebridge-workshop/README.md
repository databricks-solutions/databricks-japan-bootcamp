# Lakebridge Workshop

Databricks Labs [Lakebridge](https://databrickslabs.github.io/lakebridge/) を実際に動かして、データウェアハウス / ETL システムから Databricks への移行を体験するハンズオンです。

## ゴール

Lakebridge の主要機能 (Analyzer / Transpile / Reconcile) を手を動かして理解し、自組織での移行案件に適用できる状態になる。

## シナリオ一覧

| ディレクトリ | 内容 | 所要目安 |
|---|---|---|
| [synapse/](synapse/) | Synapse T-SQL の DDL とストアドを Analyzer + 3 種 Converter (BladeBridge / Morpheus / Switch) で変換、特性を比較 | 約 50 分 |
| [reconcile/](reconcile/) | 移行前後のテーブル差分検証 (ソース非依存の独立 Lab) | 約 15 分 |
| [datastage/](datastage/) | DataStage XML ジョブを Analyzer + BladeBridge で PySpark Notebook に変換 | 約 20 分 |

推奨順序は上表の通り (Synapse → Reconcile → DataStage)。ただし各シナリオは独立しているので、興味のあるものから試しても OK。

## 前提セットアップ

各シナリオを動かす前に、ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

### Databricks ワークスペース要件

- Unity Catalog 有効化
- Serverless SQL Warehouse が使える
- Foundation Model API (Claude Sonnet) の `Can Query` 権限 (Switch で利用)
- 自分がワークスペースオーナー権限 or `CREATE CATALOG` を持つ

### 1. ローカル CLI インストール

#### 1.1 Databricks CLI (v0.250+)

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

#### 1.2 Databricks プロファイル設定

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile DEFAULT
```

ブラウザが開くので OAuth でログイン。プロファイル名は任意。以降のコマンドで `--profile` を省略した場合 `DEFAULT` が使われる。

```bash
# 疎通確認
databricks current-user me --profile DEFAULT
```

### 2. Lakebridge インストール

```bash
databricks labs install lakebridge

# バージョン確認
databricks labs lakebridge --version
```

### 3. Transpiler プラグインのインストール

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

### 4. Reconcile 設定

[reconcile/](reconcile/) シナリオで使う。

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

## Lakebridge / 各 Transpiler の使い分け早見表

| 対象 | 推奨 Converter | 理由 |
|---|---|---|
| DDL (テーブル定義) | BladeBridge / Morpheus | ルールベースで決定論的・低コスト |
| 定型 SQL (単純 SELECT / UPDATE) | BladeBridge / Morpheus | 同上 |
| 複雑ストアド (動的 SQL / TRY-CATCH / sp_executesql) | **Switch (LLM)** | 意味的に等価な書き換えが必要 |
| DataStage / SSIS (XML メタデータ) | **BladeBridge** | Lakebridge 公式サポートは現時点で BladeBridge のみ |
| mssql / snowflake / synapse の SQL | Morpheus (Databricks 純正) 優先、ダメなら BladeBridge | 純正ゆえ追従速度が速い |

Analyzer の `llm_support_needed = true` フラグが Switch を充てる根拠になる。

## トラブルシュート

### `transpile` コマンドが `EOFError` で落ちる

非インタラクティブ環境 (CI など) で `Select the transpiler:` プロンプトが待てずに落ちる。明示的に config-path を指定する。

```bash
# BladeBridge
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml

# Morpheus
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml
```

### `databricks labs lakebridge describe-transpile` に Morpheus / Switch が出ない

`install-transpile` 実行時に `All` を選んでいない可能性。再度:

```bash
databricks labs lakebridge install-transpile --profile DEFAULT
```

### Switch Job が Foundation Model で失敗する

ワークスペースで `databricks-claude-sonnet-4` エンドポイントへの `Can Query` 権限を確認。権限が無ければワークスペース管理者に付与依頼。

### Reconcile のレポートテーブルが見つからない

`configure-reconcile` で指定した metadata catalog/schema を `databricks labs lakebridge configure-reconcile --profile DEFAULT` で再確認。既定は `remorph_reconcile`。

## 参考

- Lakebridge 公式ドキュメント: https://databrickslabs.github.io/lakebridge/
- Switch (Lakebridge の pluggable transpiler): https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/
- `databricks labs lakebridge describe-transpile` で利用可能な transpiler と dialect を常に確認できる
