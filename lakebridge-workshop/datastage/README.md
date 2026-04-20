# DataStage → Databricks ハンズオン (オプション)

IBM DataStage ジョブの XML エクスポートを Databricks PySpark Notebook に変換する。**BladeBridge は Lakebridge で DataStage に対応する唯一の transpiler** なので、Synapse シナリオのような 3 種比較はせず、Analyzer → BladeBridge の 2 ステップで押さえる。

所要目安: 約 20 分

## インプット

`input/xml/` に **無毒化済みの DataStage XML 2 本** を配置済。

- `DEMO_JOB_01.xml` (シンプル、約 730 行)
- `DEMO_JOB_02.xml` (やや複雑、約 1090 行)

> 実案件の DataStage XML から組織名・ホスト名・プロジェクト名などの固有情報を除去したサンプル。XML の**構造を体感する**のが目的。

---

## 1. Analyzer

### 実行

`lakebridge-workshop/datastage/` に居る前提。

```bash
databricks labs lakebridge analyze \
  --source-directory ./input/xml \
  --report-file ./out/datastage-report.xlsx \
  --source-tech "DataStage"
```

### レポート確認

`out/datastage-report.xlsx` を開く。

- **Summary**: ジョブ数 (2)、Stage 数、使用されている Stage タイプの内訳
- **StageAnalysis** 系: Transformer / Lookup / Join / Aggregator など個別 Stage の使用状況
- **Unsupported / Manual Review** 系: BladeBridge で自動変換しきれない Stage の列挙

### 学習ポイント

- 実案件の Analyzer レポートは**移行見積り / リソース計画のベース**になる
- XML を手で読むのは大変だが、Analyzer がメタ情報を抽出して Excel 化してくれる
- XML 数百本規模でも数分で完走する

---

## 2. Transpile: BladeBridge (PySpark Notebook)

DataStage に対応する transpiler は BladeBridge のみのため、**`Select the transpiler:` プロンプトは出ない** (自動選択)。

### 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect datastage \
  --input-source ./input/xml \
  --output-folder ./out/bladebridge \
  --target-technology PYSPARK
```

`--target-technology` に `PYSPARK` を指定することで、**Databricks Notebook 形式の `.py` ファイル** (`# Databricks notebook source` ヘッダー付き) が出力される。

### 生成物の確認

```
out/bladebridge/
├── DEMO_JOB_01.py      # PySpark notebook
├── DEMO_JOB_02.py
└── transpile-report.*  # 変換メトリクス
```

#### ローカルで中身を眺める

```bash
head -50 out/bladebridge/DEMO_JOB_01.py
```

`# COMMAND ----------` でセル境界が表現され、DataStage の Source Stage → Transformation → Sink Stage の流れが PySpark DataFrame 操作に落ちているのが見える。

#### Databricks Workspace にアップロードして中身確認

```bash
# 自分のユーザーホーム配下にアップロード (PATH は環境に合わせる)
databricks workspace import-dir \
  ./out/bladebridge \
  /Workspace/Users/<your-email>/lakebridge-demo/datastage-output \
  --profile DEFAULT \
  --format SOURCE \
  --language PYTHON \
  --overwrite
```

あるいは Databricks UI の **Workspace → 自分のフォルダ → (右上) Import** に `.py` をドラッグ & ドロップ。

インポート後、Notebook として開いて:

- **COMMAND セル**の区切り
- DataFrame 読み込み / 変換 / 書き出しの流れ
- DataStage 固有の Stage 型 (Transformer / Lookup) が PySpark のどの API にマッピングされているか
- `# TODO:` / `# MANUAL REVIEW:` コメントの出現箇所

を眺める。**実行までは目指さない** (ソース / シンクが本物の DB を指しているため)。あくまで**中身を開いて構造を体感する**のがゴール。

### 学習ポイント

- BladeBridge は DataStage XML → PySpark Notebook を**直接ワークスペースにインポートできる形**で出力
- 移行案件では、これを**実行可能にするまで**に人手の補完 (ソース接続、依存パラメータ、エラーハンドリング) が必要
- SSIS でも類似パターン (XML / メタデータ → PySpark Notebook) で対応可能 (experimental 扱い)

## 時間余ったら

- `--target-technology` を `SQL` に変えるとどうなるか試す
- 元 XML と生成 `.py` を並べて、どの Stage がどの関数呼び出しに化けたかを数セル追ってみる

## 参考

- Lakebridge 公式の DataStage 専用ページ: https://databrickslabs.github.io/lakebridge/docs/transpile/source_systems/datastage
- サポート対象バージョン: DataStage v8 以降 (XML エクスポート形式が v8 から一貫)
- DSX ファイルは非サポート (XML エクスポートのみ)
