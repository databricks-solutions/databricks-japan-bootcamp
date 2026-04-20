# Reconcile (データ差分検証) ハンズオン

Reconcile は**移行前後のデータが一致しているか**を機械的に検証する Lakebridge のツール。行数、スキーマ、値の 3 観点で差分レポートを Databricks テーブルに吐き出す。

本 Lab ではソース技術に依存せず、Databricks 内に source / target の 2 テーブルを用意して**差分検出の動きだけ**を押さえる (独立 Lab)。

所要目安: 約 15 分

## 手順

### 1. セットアップ SQL を実行

`setup.sql` を Databricks ワークスペースで開き、SQL Editor で実行。`main.recon_src.orders` と `main.recon_tgt.orders` が作られ、5 行分の差分が意図的に入る。

`<catalog>` / `<schema>` を自分の環境に合わせて置換してから実行すること。

### 2. 設定確認

トップ README の [前提セットアップ](../README.md#前提セットアップ) で `databricks labs lakebridge configure-reconcile` 済みのはず。未実施なら:

```bash
databricks labs lakebridge configure-reconcile
```

- Data Source: `Databricks`
- Report Type: `all`

### 3. Reconcile 実行

`config/recon_config.yaml` をあらかじめ自分の環境に合わせて編集 (catalog/schema)。

```bash
databricks labs lakebridge reconcile \
  --config-file ./config/recon_config.yaml \
  --report-type all
```

> `reconcile` コマンドが Databricks Job として走り、終了すると結果テーブルが `remorph_reconcile` (または configure 時に指定した metadata schema) に書き込まれる。

### 4. レポートの読み方

SQL Editor で以下のテーブルを順に見る (スキーマ名は configure 時の既定を想定):

```sql
-- サマリ: ジョブ単位の行数 / schema / data 差分有無
SELECT * FROM remorph_reconcile.main_details ORDER BY start_ts DESC LIMIT 5;

-- 行カウント比較
SELECT * FROM remorph_reconcile.row_count_details ORDER BY start_ts DESC LIMIT 5;

-- スキーマ比較 (今回は同一スキーマなので差分なし想定)
SELECT * FROM remorph_reconcile.schema_details ORDER BY start_ts DESC LIMIT 5;

-- データ詳細差分: missing_in_target / missing_in_source / mismatch
SELECT * FROM remorph_reconcile.details ORDER BY start_ts DESC LIMIT 50;
```

期待される結果:

- **row count**: source 10, target 9 → 差分あり
- **missing_in_target**: `order_id = 1009, 1010`
- **missing_in_source**: `order_id = 9001`
- **mismatch**: `order_id = 1003` (total_amount 差異), `order_id = 1004` (order_status 差異)

## レポートタイプの使い分け

`--report-type` は `row`, `schema`, `data`, `all` から選べる。

| タイプ | 用途 | 特徴 |
|---|---|---|
| `row` | 行数だけ早く知りたい | 最軽量、ざっくり |
| `schema` | 列定義・型の一致確認 | 移行初期のスキーマ整合検査 |
| `data` | 値単位の詳細差分 | 重いが最終検証に必須 |
| `all` | 上記全部 | 実案件では PoC 段階で多用 |

## 学習ポイント

- Reconcile は**移行後の「やり切った感」を定量化**するための標準ツール
- source/target とも Databricks 内に置けるので、「移行後のテーブル同士」の整合性チェックにも使える
- クロスシステム比較の場合、Foreign Catalog (Federation) でソースシステムを Unity Catalog に取り込めば、Reconcile 側は Databricks のまま動かせるケースが多い
- 関連 PR: [lakebridge#2367](https://github.com/databrickslabs/lakebridge/pull/2367) (Lakebase Postgres を source にするパターン、マージ後利用可)

## 次

[datastage/](../datastage/) で ETL メタデータ変換を試す (オプション)。
