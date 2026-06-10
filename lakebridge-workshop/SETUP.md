# セットアップ

各シナリオを始める前に、ローカル環境と Databricks ワークスペースの準備を済ませる。所要時間は 10〜15 分。

現行の全シナリオはローカルマシンから Lakebridge CLI を実行するため、このセットアップは共通の前提となる。reconcile シナリオのみ、追加のシナリオ固有手順 (`configure-reconcile`) が [reconcile/README.md](reconcile/README.md) の冒頭にある。

## Databricks ワークスペース要件

- **Unity Catalog** 有効化 (全シナリオ)
- **Serverless SQL Warehouse** が使える (Transpile (BladeBridge) の出力 SQL 検証、Reconcile 側の source/target 参照で利用)
- **Foundation Model API** (Claude Sonnet 系) の `Can Query` 権限 (Switch で利用)
- **ジョブクラスタを起動できる** こと (Reconcile Job は既定ではクラシックのジョブクラスタを利用する)

## 1. Databricks CLI のインストール

Databricks CLI をインストールする。OS 別の手順は [公式ドキュメント (日本語)](https://docs.databricks.com/aws/ja/dev-tools/cli/install) を参照。

インストール完了後、バージョン確認:

```bash
databricks --version
```

`v0.250.0` 以上の数字が返れば OK。

## 2. Databricks プロファイル設定

ワークスペースのホスト URL はクラウドによって形式が異なる:

- AWS: `https://<workspace-id>.cloud.databricks.com`
- Azure: `https://adb-<workspace-id>.<suffix>.azuredatabricks.net`
- GCP: `https://<workspace-id>.gcp.databricks.com`

実際の値は Databricks コンソールで確認する。以下、自分のプロファイル名を `<your-profile>` とする (任意の名前で OK)。

```bash
databricks auth login --host <your-workspace-host> --profile <your-profile>
```

ブラウザが開くので OAuth でログインする。以降のコマンドはこの `<your-profile>` を指定して実行する。

疎通確認:

```bash
databricks current-user me --profile <your-profile>
```

自分のユーザー情報が JSON で返れば OK。

### `warehouse_id` の追記

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

## 3. Lakebridge インストール

```bash
databricks labs install lakebridge --profile <your-profile>
```

完了後、使えるサブコマンド一覧を確認:

```bash
databricks labs lakebridge --help
```

`analyze / transpile / llm-transpile / install-transpile / describe-transpile / configure-reconcile / reconcile / aggregates-reconcile` などが並んでいれば OK。

## 4. Converter プラグインのインストール

Lakebridge の Converter 3 種 (BladeBridge / Morpheus / Switch) をまとめてインストールする。**`--include-llm-transpiler true` フラグを付けないと Switch (LLM ベース) はインストールされない**点に留意が必要。

```bash
databricks labs lakebridge install-transpile --include-llm-transpiler true --profile <your-profile>
```

インストール完了後、BladeBridge / Morpheus が揃っていることを確認:

```bash
databricks labs lakebridge describe-transpile --profile <your-profile>
```

出力に `Bladebridge` と `Morpheus` が並んでいれば OK。

> **Switch は `describe-transpile` には出ない**。Switch は BladeBridge / Morpheus とはアーキテクチャが異なり、Databricks ワークスペースに Job + Notebook としてデプロイされる。`llm-transpile` コマンドで利用する。

## 5. 本リポジトリを clone

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

- **対処**: ワークショップ用 host に一致するプロファイルが 1 つだけになるように `~/.databrickscfg` を整理する (重複プロファイルを削除するか、`host` を微妙に変えて衝突を回避する)。
