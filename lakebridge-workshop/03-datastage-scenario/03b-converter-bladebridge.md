# 03b. Converter: BladeBridge (DataStage → PySpark Notebook)

DataStage に対応する transpiler は BladeBridge のみのため、**Select the transpiler: プロンプトは出ない** (自動選択)。

## 実行

```bash
databricks labs lakebridge transpile \
  --source-dialect datastage \
  --input-source ./input/xml \
  --output-folder ./out/bladebridge \
  --target-technology PYSPARK
```

`--target-technology` には `PYSPARK` を指定。これで **Databricks Notebook 形式の `.py` ファイル**が出力される (`# Databricks notebook source` ヘッダー付き)。

## 生成物の確認

```
out/bladebridge/
├── DEMO_JOB_01.py      # PySpark notebook
├── DEMO_JOB_02.py
└── transpile-report.*  # 変換メトリクス
```

### ローカルで中身を眺める

```bash
head -50 out/bladebridge/DEMO_JOB_01.py
```

`# COMMAND ----------` でセル境界が表現され、DataStage の Source Stage → Transformation → Sink Stage の流れが PySpark DataFrame 操作に落ちているのが見える。

### Databricks Workspace にアップロードして中身確認

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

あるいは Databricks UI で **Workspace → 自分のフォルダ → (右上) Import** に `.py` をドラッグ&ドロップ。

インポート後、Notebook として開いて:
- **COMMAND セル**の区切り
- DataFrame 読み込み / 変換 / 書き出しの流れ
- DataStage 固有の Stage 型 (Transformer / Lookup) が PySpark のどの API にマッピングされているか
- `# TODO:` / `# MANUAL REVIEW:` コメントの出現箇所

を眺める。**実行までは目指さない** (ソース/シンクが本物の DB を指しているため)。あくまで**中身を開いて構造を体感する**のがゴール。

## 学習ポイント

- BladeBridge は DataStage XML → PySpark Notebook を**直接ワークスペースにインポートできる形**で吐く
- 移行案件では、これを**実行可能にするまで**に人手の補完 (ソース接続、依存パラメータ、エラーハンドリング) が必要
- Informatica / SSIS でも同じパターン (XML / メタデータ → PySpark Notebook)

## 時間余ったら

- `target-technology` を `SQL` に変えるとどうなるか試す
- 元 XML と生成 `.py` を並べて、どの Stage がどの関数呼び出しに化けたかを数セル追ってみる
