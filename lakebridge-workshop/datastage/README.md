# DataStage から Databricks への移行ハンズオン

IBM DataStage ジョブの XML エクスポートを、Databricks の PySpark Notebook に変換する。Lakebridge で DataStage を対応ソースとして正式サポートしているのは BladeBridge。Switch (LLM ベース) でもカスタムプロンプトを書けば対応できる余地はあるが、DataStage XML は GUI 配置情報などの要素を多く含んで 1 本のサイズが大きく、ビジネスロジック部分の抽出などの前処理を挟まないと LLM では扱いにくい。BladeBridge はまさにこの前処理を組み込みで吸収してくれるため、DataStage には BladeBridge を使うのが推奨。本シナリオは Analyzer → BladeBridge の 2 ステップで進める。

## インプット

`input/xml/` に以下の DataStage XML サンプルを配置済み (組織名・ホスト名・プロジェクト名などの固有情報は含まない)。

| ファイル | 内容 |
|---|---|
| `SAMPLE_JOB.xml` | DB2 Connector を使った Source → Target の最小構成 (約 730 行) |

---

## Analyzer

### 実行

まず作業ディレクトリに移動し、出力先ディレクトリを用意する:

```bash
cd lakebridge-workshop/datastage/
mkdir -p out
```

次に `analyze` のオプションを確認する:

```bash
databricks labs lakebridge analyze --help
```

主要フラグ (`--source-directory` / `--report-file` / `--source-tech`) が一覧で表示される。今回は DataStage を対象にするので、以下のように実行する:

```bash
databricks labs lakebridge analyze \
  --source-directory ./input/xml \
  --report-file ./out/datastage-report.xlsx \
  --source-tech "Datastage" \
  --profile <your-profile>
```

### レポート確認

`out/datastage-report.xlsx` を開く。シートは多数あるが、最初は以下を中心に見ていく:

| シート | 見る観点 |
|---|---|
| `Summary` | ジョブ総数、ノード数、Complexity カテゴリの内訳 |
| `Job Details` | ジョブ 1 行 1 件、**`Categorization` (LOW / MEDIUM / HIGH / VERY_HIGH)** と `Number of Nodes` で移行難度を判断 |
| `Transformations` | 使われている Stage 種別と **`Supported?`** 列 (BladeBridge で変換可能か) と **`Mapped Type`** (Databricks 側のマッピング先) |
| `Embedded SQL Programs` | Stage 内に埋め込まれた SQL (SELECT など) の複雑度 |
| `Transformation Expressions` | Transformer Stage 内の式 (derivation) の抽出 |

### 学習ポイント

- Analyzer レポートは**移行の見積りやリソース計画の出発点**として使える
- XML を目視で追うのは大変だが、Analyzer がメタ情報を抽出して Excel にまとめてくれる
- `Transformations.Supported?` が `No` の Stage 種別は、BladeBridge がそのまま変換できないため個別対応の検討対象になる

---

## Transpile: BladeBridge (PySpark Notebook)

DataStage に対応する transpiler は BladeBridge のみなので、**`Select the transpiler:` プロンプトは出ない** (自動で BladeBridge が選ばれる)。

### 実行

```bash
mkdir -p out/bladebridge
databricks labs lakebridge transpile \
  --source-dialect datastage \
  --input-source ./input/xml \
  --output-folder ./out/bladebridge \
  --target-technology PYSPARK \
  --profile <your-profile>
```

`--target-technology` に `PYSPARK` を指定することで、**Databricks Notebook 形式の `.py` ファイル** (`# Databricks notebook source` ヘッダ付き) が出力される。

### 出力の確認

```
out/bladebridge/
├── SAMPLE_JOB.py                         # PySpark notebook (入力 XML 1 本に対応)
└── databricks_conversion_supplements.py  # 共通ユーティリティ (column renaming 等)
```

**変換サマリは stdout の 1 行テーブル** (`total_files_processed / parsing_error_count / validation_error_count / generation_error_count / ...`) のみで、別 report や error log ファイルは出力されない。

### ローカルで中身を眺める

```bash
head -50 out/bladebridge/SAMPLE_JOB.py
```

`# COMMAND ----------` でセル境界が表現され、以下が PySpark のコードに置き換わっているのが見える:

- **パラメータ**: DataStage の Job Parameters が `dbutils.widgets.text(...)` に展開される
- **Source Stage**: `spark.sql("""SELECT ...""")` として DB2 からの SELECT が再現される
- **Target Stage**: `DataFrame.write.saveAsTable(...)` として出力される

### Databricks Workspace に取り込んで中身を見る

基本は UI から手動で取り込む:

- Databricks UI の **Workspace → 自分のフォルダ → (右上) Import** を開き、生成された `SAMPLE_JOB.py` をドラッグ & ドロップ

インポート後、Notebook として開き、以下を眺める:

- **COMMAND セル**の区切り
- DataStage の Source Stage → Target Stage の流れが、PySpark のどの API に対応しているか
- パラメータが `dbutils.widgets` にどう置き換わっているか

**実行までは目指さない** (ソース / シンクの接続先は生成されたコード上では文字列で、そのままでは実体がないため)。**中身を開いて構造を確認する**のがゴール。

### 学習ポイント

- BladeBridge は DataStage XML から PySpark Notebook を**直接ワークスペースにインポートできる形**で生成する
- 生成された PySpark を**そのまま実行できる状態にする**には、人手での補完 (ソース接続、依存パラメータ、エラーハンドリングなど) が必要
- SSIS などの ETL ツールでも同様のパターン (XML / メタデータ → PySpark Notebook) で変換できる

## 時間に余裕があれば

- `--target-technology` を `SQL` に変えたときの出力を比較する
- 元 XML の `<Property Name="XMLProperties">` 内の埋め込み SELECT 文と、生成された `.py` の `spark.sql(...)` を並べて確認する

## 参考

- Lakebridge 公式の DataStage 専用ページ: https://databrickslabs.github.io/lakebridge/docs/transpile/source_systems/datastage
- サポート対象バージョン: DataStage v8 以降 (XML エクスポート形式が v8 から一貫)
- DSX ファイルは非サポート (XML エクスポートのみ)
