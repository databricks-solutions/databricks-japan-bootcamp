# Reconcile (データ差分検証) ハンズオン

Reconcile は**移行前後のデータが一致しているか**を機械的に検証する Lakebridge のツール。行数、スキーマ、値の 3 観点で差分レポートを Databricks テーブルに出力する。

本 Lab では、外部のソースシステムを用意せず、Databricks 内に source / target の 2 テーブルを作って**差分検出の挙動だけ**を押さえる。

> 既定では、Reconcile Job はサーバーレス非対応で、実行のたびにジョブクラスタ (クラシック、2-10 worker) が自動起動する。**クラスタ起動込みで初回は 5〜15 分**程度を見ておく (起動済みクラスタを使い回す手順は後述)。

## 手順

### 1. ワークスペース上の Lakebridge 構成を確認

`configure-reconcile` を既に済ませている前提で、この時点でのワークスペースには以下の構成でファイルが置かれている:

```
/Users/<your-email>/.lakebridge/
├── reconcile.yml              # Reconcile 全体設定 (configure-reconcile で生成)
├── dashboards/                # 結果可視化の AI/BI ダッシュボード
├── switch/                    # Switch transpiler のリソース (install-transpile 時)
├── wheels/                    # Lakebridge 本体 wheel
├── version.json
├── state.json
└── applied-upgrades.json      # Lakebridge 内部管理
```

`reconcile.yml` を開くと、`configure-reconcile` で入力した値が以下のような YAML で保存されていることが分かる。以降の `reconcile` コマンドはこのファイルを自動で読む。

```yaml
data_source: databricks
database_config:
  source_catalog: <your_catalog>
  source_schema: reconcile_source
  target_catalog: <your_catalog>
  target_schema: reconcile_target
metadata_config:
  catalog: <your_catalog>
  schema: reconcile
  volume: reconcile_volume
report_type: all
secret_scope: remorph_databricks
version: 1
```

### 2. セットアップ Notebook を実行

`setup.sql` は、差分検出を試すための **source / target 2 テーブルを Databricks 内に作る Notebook**。target 側には意図的な差分 (行欠落 2 件、余分な行 1 件、値差異 2 件の計 5 行分) を仕込む。

`setup.sql` を Databricks ワークスペースの任意の場所に import する (UI から手動で)。Notebook を開いてサーバーレスコンピュート (または汎用クラスタ) にアタッチしたら、以下の流れで実行する。

1. **最初のウィジェット定義セルを実行**。画面上部に 3 つのウィジェットが現れる。
2. 出てきたウィジェットに値を入れる。値は Reconcile のセットアップ時 (`configure-reconcile`) で指定した catalog/schema と合わせる。

   | ウィジェット | 説明 | 例 |
   |---|---|---|
   | `catalog` | 使用する Unity Catalog 名 | `<your_catalog>` |
   | `source_schema` | Source テーブルを置くスキーマ | `reconcile_source` |
   | `target_schema` | Target テーブルを置くスキーマ | `reconcile_target` |

3. **Run All** で残りのセルを順に実行する。

実行後、以下の 2 テーブルが作成される (行数の違いに加え、一致行のうち 2 行に値差異が仕込んである。計 5 行分の差異):

- source: `<catalog>.<source_schema>.orders` (10 行)
- target: `<catalog>.<target_schema>.orders` (9 行)

### 3. テーブル設定 JSON をワークスペースに配置

`reconcile` コマンドは `reconcile.yml` とは別に、**比較対象のテーブルを指定した JSON** をワークスペース上の決まったパスから読む。`configure-reconcile` はこの JSON を自動生成しないため、ここで手動で配置する。

命名規則・構造・全オプションは公式 Docs ([Reconcile Guide](https://databrickslabs.github.io/lakebridge/docs/reconcile/) / [Reconcile Configuration](https://databrickslabs.github.io/lakebridge/docs/reconcile/reconcile_configuration/)) を参照。以下は本 Lab で使う最小構成の要点のみ。

**配置先と命名規則:**

- 配置先: `/Users/<your-email>/.lakebridge/`
- ファイル名: `recon_config_<data_source>_<source_catalog_or_schema>_<report_type>.json`
  - 例 (`report_type = all`、source catalog が `<your_catalog>`): `recon_config_databricks_<your_catalog>_all.json`
- 内容: `{"tables": [...]}` の形式 (データベース接続情報は `reconcile.yml` 側にあるのでここでは不要)

**手順:**

1. 本リポジトリの `config/recon_tables.json` をテンプレートとして使う (テーブル構成を変えたい場合は編集)
2. Databricks ワークスペース UI で `/Users/<your-email>/.lakebridge/` を開く
3. `config/recon_tables.json` を上記 UI にドラッグ & ドロップで import し、ファイル名を命名規則に沿って変更する (例: `recon_config_databricks_<your_catalog>_all.json`)

### 4. Reconcile 実行

```bash
databricks labs lakebridge reconcile --profile <your-profile>
```

`reconcile` コマンドに `--config-file` / `--report-type` などのフラグは**無い** (`reconcile.yml` と配置済み JSON を参照する)。最後に Job URL をブラウザで開くか聞かれる。`yes` で Job 画面が開く、`no` で CLI 側に戻る (どちらを選んでも結果には影響しない)。

Job が Databricks Job として実行され、ジョブクラスタの起動込みで**初回は 5〜15 分**ほどで完了する。終了後、`configure-reconcile` で指定した metadata catalog/schema (既定 `remorph.reconcile`) 配下の 6 テーブルに結果が書き込まれる。

> **Tips**: 既定では Reconciliation Runner Job は実行のたびにクラシックの new_cluster を起動するが、Databricks Jobs UI からジョブのタスクを「**既存の汎用クラスタ (All-purpose Cluster)**」に切り替えると、起動済みのクラスタを使い回せる。クラスタ起動待ちがなくなり、2 回目以降は 2 分程度で完了する。Reconcile を素早く繰り返したいときに便利。

### 5. レポートの確認

`configure-reconcile` 実行時にワークスペース上に自動作成された **AI/BI ダッシュボード**を開いて結果を可視化するのが基本の動線。

- `LAKEBRIDGE_Reconciliation_Metrics` (通常の reconcile 結果)
- `LAKEBRIDGE_Aggregate_Reconciliation_Metrics` (`aggregates-reconcile` コマンド用、本 Lab では空)

ダッシュボードでは行数差・値差・スキーマ比較の結果をまとめて確認できる。

SQL で深掘りしたい場合は、metadata catalog/schema (既定 `remorph.reconcile`) 配下の 3 テーブルを見る (`aggregate_*` 系は `aggregates-reconcile` コマンド用で本 Lab では空):

| テーブル | 役割 |
|---|---|
| `main` | ジョブ 1 回分のメタ (recon_id / source_table / target_table / start_ts) |
| `metrics` | 行数・差分・スキーマ比較のサマリ。**まずここを見る** |
| `details` | 個別差分レコード (`recon_type` = `schema` / `mismatch` / `missing_in_source` / `missing_in_target`) |

**サマリ確認クエリ (metrics):**

```sql
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
```

個別の差分レコードまで見たい場合は `details` を参照 (`data` 列は `ARRAY<MAP<STRING, STRING>>` のため `CAST(data AS STRING)` で閲覧):

```sql
SELECT recon_type, CAST(data AS STRING) AS data_str
FROM <catalog>.<schema>.details
WHERE inserted_ts = (SELECT MAX(inserted_ts) FROM <catalog>.<schema>.details)
ORDER BY recon_type;
```

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

## 学習ポイント

- Reconcile は**移行前後のテーブルが本当に一致しているか**を機械的に確認するための標準ツール
- source/target を両方 Databricks 内に置けるほか (本 Lab の構成)、「移行後のテーブル同士」の整合性チェックにも使える
- クロスシステム比較 (例: source = Synapse, target = Databricks) の場合、現状は Reconcile 側から外部システムに JDBC で直接接続する構成になっているため**クラシッククラスタ前提**。Foreign Catalog (Federation) 経由でソースを Unity Catalog から読めるようにする拡張は [lakebridge#2367](https://github.com/databrickslabs/lakebridge/pull/2367) で進行中 (現状は PR レビュー中、マージ後に利用可能)

### レポートタイプの切り替え (補足)

本 Lab では `all` で進めているが、`configure-reconcile` の `Report Type` で以下の 4 種類から選べる (各タイプの定義は公式 Docs [Reconcile Guide](https://databrickslabs.github.io/lakebridge/docs/reconcile/) 参照):

| タイプ | 用途 | 特徴 |
|---|---|---|
| `row` | 行数だけ早く知りたい | 最軽量 |
| `schema` | 列定義・型の一致確認 | 移行初期のスキーマ整合検査 |
| `data` | 値単位の詳細差分 | 重いが最終検証に必須 |
| `all` | 上記全部 | 実案件では PoC 段階で多用 |

### Notebook API での実行 (参考)

本 Lab では CLI (`databricks labs lakebridge reconcile`) + JSON ファイルの組み合わせで実行しているが、もう 1 つ**公式サポートされた方法**として、Notebook 内で Python API を直接呼ぶルートがある。

- JSON ファイル不要 (config は Python オブジェクト `ReconcileConfig` / `TableRecon` で組み立てる)
- Notebook のアタッチ先コンピュートで実行される (Job を別途起動しない)
- 詳細: 公式 Docs [Running Reconcile on Notebook](https://databrickslabs.github.io/lakebridge/docs/reconcile/recon_notebook/)

CLI 方式と Notebook 方式は用途で使い分けると良い: 定型的な再実行やスケジュール実行には CLI 方式、config を柔軟に組み立てて試行錯誤したい場面には Notebook 方式。

## トラブルシュート

### `reconcile` コマンドが `unknown flag: --config-file` で落ちる

- **問題**: `databricks labs lakebridge reconcile --config-file ...` が `unknown flag: --config-file` で落ちる。
- **原因**: `reconcile` コマンドには `--config-file` / `--report-type` などのフラグは無い。
- **対処**: 手順 3 のとおり、対象テーブル設定は JSON としてワークスペース上の `/Users/<your-email>/.lakebridge/` に配置する。report_type は `configure-reconcile` 時に指定した `reconcile.yml` 側で決まる。

### 結果テーブルが見つからない / 名前が違う

- **問題**: `remorph_reconcile.main_details` のような名前で結果が見つからない。
- **原因**: 実際は `configure-reconcile` で指定した metadata catalog/schema (既定 `remorph.reconcile`) 配下に、`main` / `metrics` / `details` / `aggregate_metrics` / `aggregate_details` / `aggregate_rules` の 6 テーブルが作られる。
- **対処**: `/Users/<your-email>/.lakebridge/reconcile.yml` で現在の metadata 指定値を確認し、その配下のテーブル名を使う。

### Job が 10 分以上 RUNNING のまま

- **問題**: Reconcile Job が長時間 `RUNNING` のまま終わらない。
- **原因**: Reconcile Job はクラシックの new_cluster を自動起動する (サーバーレス非対応)。クラスタ起動 + ライブラリインストールで数分、ピーク時はクラスタ空き待ちでさらに数分追加される。
- **対処**: Job URL を UI で開き、クラスタの起動状態を確認する。通常は 5〜15 分程度で完了する。
