# データエンジニアリングワークショップ — Auto Loader と PySpark で作るデータパイプライン（Free Edition 版）

決済不正検知を題材に、**取り込み（Auto Loader）→ 変換（PySpark / Spark SQL）→ 集計（Gold）→ 可視化（AI/BI）→ オーケストレーション（Lakeflow Jobs）** を一気通貫で体験します。

このフォルダは **Databricks Free Edition** での単独実行に対応した版です。共有カタログ・参加者グループ・管理者による事前準備は不要で、**各参加者がそれぞれ自分の Free Edition** で、サンプルデータを**生成ノートで自分の Volume に生成**して実施します。

## 前提（Free Edition）

- カタログ・スキーマは固定: **`workspace.de_workshop`**（`workspace` は Free Edition の既定カタログ）
- コンピュートは**サーバーレス**（クラスター作成は不要）
- 外部 S3 は使わず、**マネージドストレージ上の Volume** にサンプルデータを生成して取り込む
- `samples.bakehouse.*` / `samples.wanderbricks.*` などの公開サンプルは読み取り可能

## フォルダ構成

```
de_workshop/
  05_setup.py                     … 初期セットアップ（Volume 作成 + サンプルデータ生成 + マスター取込）
  10_bronze_autoloader.py         … Auto Loader で landing Volume から Bronze 取り込み（増分対応）
  20_silver_cleanse_and_join.py   … マスター結合・クレンジング（PK/FK・Liquid Clustering）
  30_gold_aggregations.py         … 顧客/加盟店/決済手段/日次の集計（Gold）
```

> データは `05_setup` が **PySpark のみ**で生成します（`workspace.de_workshop.landing` / `master` に Parquet 出力、`t_payments` 約 10 万件）。dbldatagen・手動アップロード・`sample_data` 同梱は不要です。生成は冪等で、既に生成済みならスキップします。増分（7 月分）も `10_bronze_autoloader` 内で生成するため、別途の生成ノートは不要です。

## 実施手順

1. **クローン**: このリポジトリ（`https://github.com/databricks-solutions/databricks-japan-bootcamp`）をワークスペースに Git folder でクローン（Sparse checkout path: `databricks-data-ai-bootcamp/20260911`）。
2. **`05_setup` を実行**: スキーマ `workspace.de_workshop` と Volume（`landing`/`master`/`checkpoints`）の作成、**サンプルデータ生成**（マスター3表・ファクト4表）、`master` からの Bronze マスター取込（PK 付き）までを **自動で実施**（サーバーレスで「すべてを実行」）。冪等なので再実行しても再生成しません。
3. **`10_bronze_autoloader` を上から順に実行**: Auto Loader で初期データを取り込み（1 回目）→ **ノートブック内で増分（7 月分）を生成** → 同じ取り込みコードを再実行（2 回目）まで一連で走り、追加分だけが取り込まれること（Exactly-once）を確認できる。
4. **`20_silver` → `30_gold`** を順に実行（マスター結合・クレンジング・集計）。
5. **可視化 / オーケストレーション**: AI/BI ダッシュボード（Genie Code）と Lakeflow Jobs は説明資料の手順に沿って実施（ダッシュボード更新タスクの SQL ウェアハウスは Free 既定の **Serverless Starter Warehouse** を使用）。

> Free Edition で動作検証済み: Auto Loader（Volume・ディレクトリリスティング・増分/Exactly-once）、Liquid Clustering、PK/FK 制約、Predictive Optimization、サーバーレス実行。外部 S3 / External Location は Free 非対応のため、データは Volume 上に生成する方式にしています。
