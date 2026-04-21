# Reconcile (データ差分検証) ハンズオン

Reconcile は**移行前後のデータが一致しているか**を機械的に検証する Lakebridge のツール。行数、スキーマ、値の 3 観点で差分レポートを Databricks テーブルに吐き出す。

本 Lab ではソース技術に依存せず、Databricks 内に source / target の 2 テーブルを用意して**差分検出の動きだけ**を押さえる (独立 Lab)。

所要目安: 約 20 分 (Job cluster 起動 3〜5 分 + 実行 + 確認)

> Reconcile Job は現在 serverless 非対応で、**classic new_cluster (2-10 worker)** を毎回起動する。**初回は 3〜5 分**の cluster 起動待ちが発生する点に注意。

## 手順

### 1. セットアップ SQL を実行

`setup.sql` を開き、冒頭の注意書きに従って `<catalog>` / `<schema>` 相当箇所を自分の環境に書き換えてから SQL Editor で実行する。

source/target は**前提セットアップ** ([トップ README 参照](../README.md#5-reconcile-設定)) の `configure-reconcile` 時に指定した catalog/schema と一致させる。例えば:

- source: `<your_catalog>.reconcile_source.orders` (10 行)
- target: `<your_catalog>.reconcile_target.orders` (9 行、意図的に 5 行分の差分)

### 2. Reconcile 設定の確認

トップ README の [前提セットアップ](../README.md#5-reconcile-設定) で `configure-reconcile` 済みのはず。未実施なら:

```bash
databricks labs lakebridge configure-reconcile --profile <your-profile>
```

実行すると対話プロンプトが 9 段階続く。主なポイントのみ抜粋:

| 項目 | 選択 / 入力 |
|---|---|
| Data Source | `databricks` |
| Report Type | `all` |
| Secret scope | 既定 (`remorph_databricks`) |
| Source catalog / schema | 1 の setup.sql で作った source 側 (例: `<your_catalog>` / `reconcile_source`) |
| Target catalog / schema | 1 の setup.sql で作った target 側 (例: `<your_catalog>` / `reconcile_target`) |
| Metadata catalog / schema / volume | **既定は `remorph` / `reconcile` / `reconcile_volume`** (存在しなければ作成確認あり) |

ここで確定した値は workspace の `/Users/<you>/.lakebridge/reconcile.yml` に保存され、以降の `reconcile` コマンドがそれを参照する。

### 3. テーブル設定 JSON を workspace にアップロード

`reconcile` コマンドは `reconcile.yml` (グローバル設定) に加え、**対象テーブルを指定した JSON** を workspace 上の決まったパスから読む。

- ファイル名: **`recon_config_<data_source>_<source_catalog_or_schema>_<report_type>.json`**
  - 例: `recon_config_databricks_<your_catalog>_all.json`
- 配置場所: `/Users/<your-email>/.lakebridge/`
- フォーマット: JSON、`{"tables": [...]}` のみでよい (database_config 系は `reconcile.yml` 側)

このリポに `config/recon_tables.json` をテンプレとして置いてある (ファイル名は `*conf*.json` gitignore パターン回避のため `recon_tables.json`)。そのまま使う場合:

```bash
# <your_catalog> を自分の catalog 名に置換
databricks workspace import \
  /Users/<your-email>/.lakebridge/recon_config_databricks_<your_catalog>_all.json \
  --file ./config/recon_tables.json \
  --format AUTO --overwrite \
  --profile <your-profile>
```

> テーブル構造を変えたい場合は `config/recon_tables.json` を編集してから import する。

### 4. Reconcile 実行

```bash
databricks labs lakebridge reconcile --profile <your-profile>
```

`reconcile` コマンドには `--config-file` / `--report-type` などのフラグは**無い** (`reconcile.yml` と upload 済み JSON を見る)。最後に Job URL をブラウザで開くか聞かれるので `no` で OK。

Job が Databricks Job として走り、classic new_cluster の起動込みで 3〜5 分で完了する。終了後、`<metadata_catalog>.<metadata_schema>` (既定 `remorph.reconcile`) 配下の 6 テーブルに結果が書き込まれる。

### 5. レポートの読み方

以下の 3 テーブルが実用的 (`aggregate_*` テーブルは `aggregates-reconcile` コマンド用、本 Lab では空)。

> `<catalog>.<schema>` は configure-reconcile で入力した metadata の値に置換。既定なら `remorph.reconcile`。

```sql
-- (a) main: ジョブ 1 回分の meta (recon_id / source_table / target_table / report_type / start_ts)
SELECT recon_id, source_type, report_type, start_ts
FROM <catalog>.<schema>.main
ORDER BY start_ts DESC LIMIT 5;

-- (b) metrics: 行数・差分・スキーマ比較のサマリ (struct 多階層)
SELECT
  recon_metrics.source_record_count AS src_cnt,
  recon_metrics.target_record_count AS tgt_cnt,
  recon_metrics.row_comparison.missing_in_source  AS missing_in_src,
  recon_metrics.row_comparison.missing_in_target  AS missing_in_tgt,
  recon_metrics.column_comparison.absolute_mismatch AS mismatch,
  recon_metrics.column_comparison.mismatch_columns  AS mismatch_cols,
  recon_metrics.schema_comparison AS schema_ok,
  run_metrics.status AS overall_ok
FROM <catalog>.<schema>.metrics
ORDER BY inserted_ts DESC LIMIT 1;

-- (c) details: 個別差分レコード。`data` 列は ARRAY<MAP<STRING, STRING>> なので CAST して覗く
SELECT recon_type, CAST(data AS STRING) AS data_str
FROM <catalog>.<schema>.details
WHERE inserted_ts = (SELECT MAX(inserted_ts) FROM <catalog>.<schema>.details)
ORDER BY recon_type;
```

`recon_type` は 4 種: `schema` / `mismatch` / `missing_in_source` / `missing_in_target`。

### 期待される結果

| 観点 | 期待値 |
|---|---|
| `src_cnt` / `tgt_cnt` | 10 / 9 |
| `missing_in_src` | 1 (order_id=9001) |
| `missing_in_tgt` | 2 (order_id=1009, 1010) |
| `mismatch` | 2 (order_id=1003 total_amount, 1004 order_status) |
| `mismatch_cols` | `order_status, total_amount` |
| `schema_ok` | true |
| `overall_ok` | **false** (差分ありのため) |

## レポートタイプの使い分け

`configure-reconcile` の `Report Type` で選ぶ (本 Lab では `all`)。

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

## トラブルシュート

### Reconcile コマンドが `unknown flag: --config-file` で落ちる

Lakebridge の `reconcile` コマンドには `--config-file` / `--report-type` などの引数は無い。テーブル設定は 3 節のとおり workspace に JSON として置き、report_type は `reconcile.yml` 側で指定する。

### 結果テーブルが見つからない / 教材と名前が違う

教材の一部ドキュメントで `remorph_reconcile` / `main_details` 等の名前が出る場合があるが、実際は:

- カタログ・スキーマ: `configure-reconcile` で指定した値 (既定は catalog=`remorph` schema=`reconcile`)
- テーブル: `main` / `metrics` / `details` / `aggregate_metrics` / `aggregate_details` / `aggregate_rules`

### Job が 10 分以上 RUNNING のまま

Reconcile Job は classic new_cluster を自動起動する (serverless 非対応)。初回起動 + ライブラリインストールで 3〜5 分、ピーク時はクラスタ空き待ちでさらに数分かかることがある。Job URL を UI で開いて cluster 状態を確認。

## 次

[datastage/](../datastage/) で ETL メタデータ変換を試す (オプション)。
