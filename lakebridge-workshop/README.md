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

推奨順序は **Synapse → Reconcile → DataStage** だが、各シナリオは独立しているので、興味のあるものから着手しても構わない。

## 前提セットアップ

ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

### Databricks ワークスペース要件

- **Unity Catalog** 有効化 (全シナリオ)
- **Serverless SQL Warehouse** が使える (Transpile (BladeBridge) の出力 SQL 検証、Reconcile 側の source/target 参照で利用)
- **Foundation Model API** (Claude Sonnet 系) の `Can Query` 権限 (Switch で利用)
- **ジョブクラスタを起動できる** こと (Reconcile Job は serverless 非対応で、実行時に classic クラスタを自動起動する)

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

#### `warehouse_id` の追記

Lakebridge の `transpile` は出力 SQL の検証に SQL Warehouse を使うため、プロファイルに `warehouse_id` を設定しておく。

```bash
# Warehouse ID (Serverless SQL Warehouse を推奨)
databricks warehouses list --profile <your-profile>
```

`~/.databrickscfg` を開き、`[<your-profile>]` セクションに 1 行追記する (auth 関連の行は `databricks auth login` が既に書いているので維持):

```ini
[<your-profile>]
host         = https://<your-workspace-host>
...
warehouse_id = abc123def456ghi7
```

### 3. Lakebridge インストール

```bash
databricks labs install lakebridge --profile <your-profile>
```

完了後、使えるサブコマンド一覧を確認:

```bash
databricks labs lakebridge --help
```

`analyze / transpile / llm-transpile / install-transpile / describe-transpile / configure-reconcile / reconcile / aggregates-reconcile` などが並んでいれば OK。

### 4. Transpiler プラグインのインストール

Lakebridge の Transpiler 3 種 (BladeBridge / Morpheus / Switch) をまとめてインストールする。**`--include-llm-transpiler true` フラグを付けないと Switch (LLM ベース) は入らない**。

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile <your-profile>
```

インストール完了後、BladeBridge / Morpheus が揃っていることを確認:

```bash
databricks labs lakebridge describe-transpile --profile <your-profile>
```

出力に `Bladebridge` と `Morpheus` が並んでいれば OK。

> **Switch は `describe-transpile` には出ない**。Switch は workspace 側に Job + Notebook としてデプロイされる pluggable transpiler で、BladeBridge / Morpheus とはアーキテクチャが違う。`llm-transpile` コマンドで利用する。

### 5. Reconcile 設定

```bash
databricks labs lakebridge configure-reconcile --profile <your-profile>
```

対話プロンプトが 9 段階続く。主な入力ポイント:

| 項目 | 入力 |
|---|---|
| Data Source | `databricks` (0) |
| Report Type | `all` (0) |
| Secret scope | 既定 (`remorph_databricks`) |
| Source catalog / schema | Reconcile Lab で使う source 側 (例: `<your_catalog>` / `reconcile_source`) |
| Target catalog / schema | Reconcile Lab で使う target 側 (例: `<your_catalog>` / `reconcile_target`) |
| Metadata catalog / schema / volume | **既定は `remorph` / `reconcile` / `reconcile_volume`** (存在しなければ作成確認あり) |

初回実行時、Databricks 上に以下が自動で作成される:

- **Metadata catalog/schema** 配下のテーブル 6 本 (Reconcile 結果の保存先、`aggregate_*` は `aggregates-reconcile` コマンド用):
  - `main`
  - `metrics`
  - `details`
  - `aggregate_metrics`
  - `aggregate_details`
  - `aggregate_rules`
- **ワークスペース** 上の AI/BI ダッシュボード 2 つ (上記テーブルを可視化):
  - `LAKEBRIDGE_Reconciliation_Metrics`
  - `LAKEBRIDGE_Aggregate_Reconciliation_Metrics`
- **ワークスペース** 上の Job 1 本 (`reconcile` コマンドが内部でキックする):
  - `LAKEBRIDGE_Reconciliation_Runner`

### 6. 本リポジトリを clone

各シナリオの入力データと README を手元に置くため、本リポジトリを clone する。

```bash
git clone https://github.com/databricks-solutions/databricks-japan-bootcamp.git
cd databricks-japan-bootcamp/lakebridge-workshop
```

ここまで完了すれば、各シナリオに進める。

## トラブルシュート

### 同じ host を指すプロファイルが複数あってインストールが失敗する

- **問題**: `databricks labs install lakebridge` が以下のエラーで落ちる。

  ```
  Error: ... match https://... in ~/.databrickscfg. Use --profile to specify which profile to use
  ```

- **原因**: `~/.databrickscfg` 内に**同じ host を指すプロファイルが複数**あり、Lakebridge 内部の host 解決が衝突する。`--profile` は外側の CLI にしか効かず、内部の SDK 呼び出しは host マッチで profile を引くため衝突を回避できない。

- **対処**: ワークショップ用 host に match するプロファイルが 1 つだけになるように `~/.databrickscfg` を整理する (重複プロファイルを削除するか、`host` を微妙に変えて衝突を回避する)。

## 参考

- Lakebridge 公式ドキュメント: https://databrickslabs.github.io/lakebridge/
- Switch (Lakebridge の pluggable transpiler): https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/
- `databricks labs lakebridge describe-transpile` で利用可能な transpiler と対応ソースを常に確認できる (Switch は除く)
