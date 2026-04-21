# DataStage から Databricks への移行ハンズオン

IBM DataStage ジョブの XML エクスポートを Databricks PySpark Notebook に変換する。Lakebridge で DataStage を dialect として正式サポートしているのは BladeBridge (Switch もカスタムプロンプトで対応の可能性はあるが、DataStage XML は 1 本あたりのサイズが大きく LLM では実用的ではない)。そのため本シナリオは Analyzer → BladeBridge の 2 ステップで押さえる。

## インプット

`input/xml/` に以下の DataStage XML サンプルを配置済み (組織名・ホスト名・プロジェクト名などの固有情報は含まない)。

| ファイル | 内容 |
|---|---|
| `SAMPLE_JOB.xml` | DB2 Connector を使った Source → Target の最小構成 (約 730 行) |

XML の**構造を体感する**のが目的。

---

## 1. Analyzer

### 実行

まず作業ディレクトリに移動する:

```bash
cd lakebridge-workshop/datastage/
```

次に `analyze` のオプションを確認:

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

`out/datastage-report.xlsx` を開く。多数のシートがあるが、最初は以下を中心に見る:

| シート | 見る観点 |
|---|---|
| `Summary` | ジョブ総数、ノード数、Complexity カテゴリの内訳 |
| `Job Details` | ジョブ 1 行 1 件、**`Categorization` (LOW / MEDIUM / HIGH / VERY_HIGH)** と `Number of Nodes` で移行難度を判断 |
| `Transformations` | 使われている Stage 種別と **`Supported?`** 列 (BladeBridge で変換可能か) + **`Mapped Type`** (Databricks 側のマッピング先) |
| `Embedded SQL Programs` | Stage 内に埋め込まれた SQL (SELECT など) の複雑度 |
| `Transformation Expressions` | Transformer Stage 内の式 (derivation) の抽出 |

### 学習ポイント

- Analyzer レポートは**移行の見積りやリソース計画の出発点**として使える
- XML を手で読むのは大変だが、Analyzer がメタ情報を抽出して Excel 化してくれる
- XML 数百本規模でも数分で完走する
- `Transformations.Supported?` が `No` の Stage 種別は、BladeBridge でそのまま変換できないので個別対応の検討対象

---

## 2. Transpile: BladeBridge (PySpark Notebook)

DataStage に対応する transpiler は BladeBridge のみのため、**`Select the transpiler:` プロンプトは出ない** (自動選択)。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect datastage \
  --input-source ./input/xml \
  --output-folder ./out/bladebridge \
  --target-technology PYSPARK \
  --profile <your-profile>
```

`--target-technology` に `PYSPARK` を指定することで、**Databricks Notebook 形式の `.py` ファイル** (`# Databricks notebook source` ヘッダ付き) が出力される。

### 生成物の確認

```
out/bladebridge/
├── SAMPLE_JOB.py                         # PySpark notebook (入力 XML 1 本に対応)
└── databricks_conversion_supplements.py  # 共通ユーティリティ (column renaming 等)
```

**BladeBridge の変換サマリは stdout の 1 行テーブル** (`total_files_processed / parsing_error_count / validation_error_count / generation_error_count / ...`) のみで、別 report や error log ファイルは生成されない。

### ローカルで中身を眺める

```bash
head -50 out/bladebridge/SAMPLE_JOB.py
```

`# COMMAND ----------` でセル境界が表現され、以下の流れが PySpark DataFrame 操作に落ちているのが見える:

- **パラメータ**: DataStage の Job Parameters が `dbutils.widgets.text(...)` に展開
- **Source Stage**: `spark.sql("""SELECT ...""")` で DB2 からの SELECT を再現
- **Target Stage**: `DataFrame.write.saveAsTable(...)` で出力

### Databricks Workspace にアップロードして中身確認

```bash
databricks workspace import-dir \
  ./out/bladebridge \
  /Workspace/Users/<your-email>/lakebridge-demo/datastage-output \
  --profile <your-profile> \
  --format SOURCE \
  --language PYTHON \
  --overwrite
```

あるいは Databricks UI の **Workspace → 自分のフォルダ → (右上) Import** に `.py` をドラッグ & ドロップ。

インポート後、Notebook として開いて以下を眺める:

- **COMMAND セル**の区切り
- DataStage の Source Stage → Target Stage の流れが PySpark のどの API にマッピングされているか
- パラメータの `dbutils.widgets` 置換

**実行までは目指さない** (ソース / シンクの接続先は生成されたコード上の文字列にすぎず、そのままでは実体がない)。あくまで**中身を開いて構造を体感する**のがゴール。

### 学習ポイント

- BladeBridge は DataStage XML → PySpark Notebook を**直接ワークスペースにインポートできる形**で出力
- 生成された PySpark を**実行可能にするまで**には人手での補完 (ソース接続、依存パラメータ、エラーハンドリング) が必要
- SSIS でも類似パターン (XML / メタデータ → PySpark Notebook) で対応可能 (experimental 扱い)

## 時間余ったら

- `--target-technology` を `SQL` に変えるとどうなるか試す
- 元 XML の `<Property Name="XMLProperties">` 内の埋め込み SELECT 文と、生成 `.py` の `spark.sql(...)` を並べて比較

## 参考

- Lakebridge 公式の DataStage 専用ページ: https://databrickslabs.github.io/lakebridge/docs/transpile/source_systems/datastage
- サポート対象バージョン: DataStage v8 以降 (XML エクスポート形式が v8 から一貫)
- DSX ファイルは非サポート (XML エクスポートのみ)
