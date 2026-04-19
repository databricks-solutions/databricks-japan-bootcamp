# 03a. Analyzer (DataStage)

## 実行

`lakebridge-workshop/03-datastage-scenario/` に居る前提。

```bash
databricks labs lakebridge analyze \
  --source-directory ./input/xml \
  --report-file ./out/datastage-report.xlsx \
  --source-tech "DataStage"
```

## レポート確認

`out/datastage-report.xlsx` を開く。

- **Summary**: ジョブ数 (2)、Stage 数、使用されている Stage タイプの内訳
- **StageAnalysis** 系: Transformer / Lookup / Join / Aggregator など個別 Stage の使用状況
- **Unsupported / Manual Review** 系: BladeBridge で自動変換しきれない Stage の列挙

## 学習ポイント

- 実案件の Analyzer レポートは**移行見積り / リソース計画のベース**になる
- XML を機械的に読むのは大変だが、Analyzer がメタ情報を抽出して Excel 化してくれる
- 既存案件の実績を見ると、XML 数百本規模でも数分で完走する

## 参考

社内 DataStage 実案件の Analyzer 結果 (無毒化前) は別途 SA 内部リポに置いてある (本ハンズオン範囲外)。

## 次

[03b: Converter - BladeBridge](03b-converter-bladebridge.md) へ。
