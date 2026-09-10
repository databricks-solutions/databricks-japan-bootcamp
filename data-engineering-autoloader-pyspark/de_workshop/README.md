# データエンジニアリングワークショップ — Auto Loader と PySpark で作るデータパイプライン（Free Edition 版）

決済不正検知を題材に、**取り込み（Auto Loader）→ 変換（PySpark / Spark SQL）→ 集計（Gold）→ 可視化（AI/BI）→ オーケストレーション（Lakeflow Jobs）** を一気通貫で体験します。

このフォルダは **Databricks Free Edition** での単独実行に対応した版です。共有カタログ・参加者グループ・管理者による事前準備は不要で、**各参加者がそれぞれ自分の Free Edition** で実施します。

## 前提（Free Edition）

- カタログ・スキーマは固定: **`workspace.de_workshop`**（`workspace` は Free Edition の既定カタログ）
- コンピュートは**サーバーレス**（クラスター作成は不要）
- 外部 S3 は使わず、**マネージドストレージ上の Volume** にサンプルファイルを**手動アップロード**して取り込む
- `samples.bakehouse.*` / `samples.wanderbricks.*` などの公開サンプルは読み取り可能（本ワークショップでは同梱サンプルを使用）

## フォルダ構成

```
de_workshop/
  05_setup.py                 … 初期セットアップ（スキーマ / Volume 作成 + マスター取込）
  10_bronze_autoloader.py     … Auto Loader で landing Volume から Bronze 取り込み（増分対応）
  20_silver_cleanse_and_join.py … マスター結合・クレンジング（PK/FK・Liquid Clustering）
  30_gold_aggregations.py     … 顧客/加盟店/決済手段/日次の集計（Gold）
  sample_data/                … 手動アップロード用サンプル（リポジトリ同梱）
    master/<table>/<table>.parquet                  … マスター3表
    landing_initial/<table>/<table>.parquet         … ファクト初期データ4表
    landing_incremental/<table>/<table>_202607.parquet … ファクト増分（7月分）4表
  admin/generate_sample_data.py … サンプル再生成用（教材メンテ・参加者は実行しない）
```

## 実施手順

1. **クローン**: このリポジトリをワークスペースに Git folder でクローン（Sparse checkout path: `data-engineering-autoloader-pyspark/de_workshop`）。
2. **`05_setup` を実行（1 回目）**: スキーマ `workspace.de_workshop` と Volume `landing` / `master` / `checkpoints` が作成される（マスターは未アップロードのためスキップ表示）。
3. **サンプルを手動アップロード**: この repo の `sample_data/` をダウンロードし、Databricks の「ボリュームにアップロード」で以下に配置する。
   - マスター: `sample_data/master/<table>/<table>.parquet` → `/Volumes/workspace/de_workshop/master/<table>/`
   - ファクト初期: `sample_data/landing_initial/<table>/<table>.parquet` → `/Volumes/workspace/de_workshop/landing/<table>/`
   - （`<table>` = `m_customers` / `m_merchants` / `m_payment_methods` / `t_payments` / `t_point_transactions` / `t_charges` / `t_login_events`）
4. **`05_setup` を再実行（2 回目）**: `master` Volume からマスターを取り込み、Bronze マスターテーブル（PK 付き）が作成される。
5. **`10_bronze_autoloader` を実行（1 回目）**: Auto Loader が `landing` の各ファクトを増分取り込みし、`bronze_t_*` を作成（件数をメモ）。
6. **増分を体験**: `sample_data/landing_incremental/<table>/<table>_202607.parquet` を `/Volumes/workspace/de_workshop/landing/<table>/batch=20260707/` にアップロードし、**`10_bronze_autoloader` を再実行（2 回目）** → 追加分だけが取り込まれることを確認。
7. **`20_silver` → `30_gold`** を順に実行（マスター結合・クレンジング・集計）。
8. **可視化 / オーケストレーション**: AI/BI ダッシュボード（Genie Code）と Lakeflow Jobs は説明資料の手順に沿って実施（ダッシュボード更新タスクの SQL ウェアハウスは Free 既定の **Serverless Starter Warehouse** を使用）。

> Free Edition で動作検証済み: Auto Loader（Volume・ディレクトリリスティング・増分/Exactly-once）、Liquid Clustering、PK/FK 制約、Predictive Optimization、サーバーレス実行。外部 S3 / External Location は Free 非対応のため、上記のとおり Volume への手動アップロード方式にしています。
