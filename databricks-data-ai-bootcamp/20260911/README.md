# Lakeflow データエンジニアリング ワークショップ

Databricks の新しいデータエンジニアリング講座へようこそ。

## 扱うテクノロジー

- **Lakeflow Spark Declarative Pipelines (SDP)** — ストリーミングテーブル、マテリアライズドビュー、データ品質エクスペクテーションを、Python と SQL で手書きします。
- **Genie Code** — 人間のレビュー（human-in-the-loop）を挟みながら AI がパイプライン作成を支援します。
- **SDP リアルタイムモード (RTM)** — サブ秒のエンドツーエンドレイテンシで動く、連続実行のサーバーレスパイプライン。

ステップバイステップの演習は [Labguide.md](./Labguide.md) を参照してください。

## 前提条件（Free Edition）

- **Databricks Free Edition**（Unity Catalog・サーバーレス有効）での単独実行を前提とします。
- 固定スキーマ `workspace.de_workshop`（`workspace` は Free Edition の既定カタログ）。まだ無ければ `CREATE SCHEMA IF NOT EXISTS workspace.de_workshop;` で作成します。
- Lab 2 用に、ボリューム `workspace.de_workshop.landing` を作成し、`booking_fraud_flags/` に不正マーカー JSON を配置済みであること（`samples.wanderbricks.booking_updates` の一部から生成）。生成手順は [`misc/setup_workshop.py`](./misc/setup_workshop.py) を参照。
