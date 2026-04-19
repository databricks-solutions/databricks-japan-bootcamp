# 01a. Analyzer (Synapse)

Analyzer は移行元コードをスキャンし、複雑度スコア・変換難易度・推奨 Converter を Excel レポートに吐き出すツール。**実際のマイグレーション案件では最初にこれを走らせる**。

## 実行

`lakebridge-workshop/01-synapse-scenario/` に居る前提。

```bash
databricks labs lakebridge analyze \
  --source-directory ./input \
  --report-file ./out/synapse-report.xlsx \
  --source-tech "Synapse"
```

プロンプトで `Select the source technology:` が出たら `Synapse` を選ぶ。
(`--source-tech` を明示すればプロンプトは出ない)

> 対応 source-tech 一覧は `databricks labs lakebridge analyze --help` で確認できる。

## 生成物の確認

```
out/
└── synapse-report.xlsx
```

Excel を開いて以下の観点でざっと眺める。

### 見るべきシート

- **Summary**: ファイル数、総行数、言語ミックス、推定工数レンジ
- **FileAnalysis** (またはシート名類似): ファイル単位のスコア
  - `complexity_score`: 複雑度 (高いほど機械変換が難しい)
  - `llm_support_needed`: `true` のファイルは Switch (LLM) 向き
  - `sql_dialect`: 検出された方言
- **Unsupported Constructs** 系: そのままでは変換できない構文リスト

### 学習ポイント

- DDL 5 本はスコアが低く、ルールベース (BladeBridge / Morpheus) で問題なく回る想定
- ストアド 2 本、特に `mssql_example2_stored_procedure.sql` (動的 SQL + TRY/CATCH + sp_executesql) はスコアが跳ね上がる → **Switch (LLM) を充てる判断根拠**になる
- 実案件ではこのレポートを顧客と共有し、「このファイルは Switch、こっちは BladeBridge で」と方針を握る

## トラブルシュート

- `analyze` が途中で止まる → `--source-directory` が絶対パスだと安定する
- Excel が開けない → `pip show openpyxl` で確認 (Lakebridge が出力に使用)

## 次

[01b: Converter - BladeBridge](01b-converter-bladebridge.md) へ。
