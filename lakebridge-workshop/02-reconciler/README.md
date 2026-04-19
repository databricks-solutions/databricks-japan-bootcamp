# Lab 2: Reconciler (独立)

Reconciler は**移行前後のデータが一致しているか**を機械的に検証するツール。行数、スキーマ、値の 3 観点で差分レポートを Databricks テーブルに吐き出す。

本 Lab ではシナリオ 1 / 3 とは独立させ、Databricks 内に source / target の 2 テーブルを用意して**差分検出の動きだけ**を押さえる。

## 手順

[02-reconciler.md](02-reconciler.md)

## 補足: Lakebase Postgres を source にするパターン

Reconciler の **真の用途** はクロスシステム比較 (例: Synapse と Databricks、Snowflake と Databricks)。Databricks は外部システムを **Foreign Catalog / Federation** で Unity Catalog に取り込めるので、Reconciler 側は Databricks のままで動かせるケースが多い。

- Lakebase Postgres を source にするパターンの PR: https://github.com/databrickslabs/lakebridge/pull/2367 (マージ後に利用可)
- Databricks 社内手順 Doc: (関山さん担当、吉村さん経由で取得)

今回は時間の関係で触れない。AMA で出たら案内する。
