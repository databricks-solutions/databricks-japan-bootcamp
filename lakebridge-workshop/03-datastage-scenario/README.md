# シナリオ 3: DataStage (オプション)

IBM InfoSphere DataStage ジョブ (XML エクスポート) を Databricks PySpark Notebook に変換する。**BladeBridge は DataStage に対応する唯一の Lakebridge transpiler** なので、シナリオ 1 のような 3 種比較はせず、Analyzer → BladeBridge の 2 ステップで押さえる。

**時間が余った場合のみ実施**。押していたらスキップして AMA へ。

## 進め方

| 手順 | 手順書 | 所要目安 |
|---|---|---|
| 3a | [Analyzer 実行](03a-analyzer.md) | 6 分 |
| 3b | [Converter: BladeBridge → PySpark Notebook](03b-converter-bladebridge.md) | 12 分 |

## インプット

`input/xml/` に **無毒化済みの DataStage XML 2 本** を配置済。

- `DEMO_JOB_01.xml` (シンプル、~730 行)
- `DEMO_JOB_02.xml` (やや複雑、~1090 行)

> 元ファイルは顧客の公開リポジトリからではなく、社内案件のデータから社名・内部ホスト名・内部プロジェクト名を除去済。今回は DataStage XML の**構造を体感する**のが目的。

## 学習ポイント

- DataStage は**ETL メタデータ (XML)** が変換対象。SQL ファイルとは別世界
- BladeBridge は**変換後 PySpark を Databricks Notebook の .py 形式で出力**する → そのままワークスペースにアップロードして開ける
- Informatica / SSIS / Talend 等の ETL ツールも同様の発想で進められる (今回は範囲外)
