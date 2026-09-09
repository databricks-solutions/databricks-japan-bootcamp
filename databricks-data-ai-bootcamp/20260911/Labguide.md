# Lakeflow で学ぶ AI 活用データエンジニアリング

**Version 2.0 - DAIS 2026**

👋 ようこそ。これは **Databricks データエンジニアリング ワークショップ**のラボガイドです。ご参加ありがとうございます。

本ワークショップでは、データエンジニアであれば誰もが身につけておくべき中核知識 — **インジェスト（取り込み）・変換・オーケストレーション** — を、各ラボに挙げた中核テクノロジーと OSS フレームワークを使って一通り学びます。

焦らず、遠慮なく質問し、何かを壊す心配はしないでください。今回利用いただく環境はあなた専用です。さっそく作っていきましょう。🚀

> **対象**: これからデータエンジニアを目指す方から中級のデータエンジニアまで。Databricks の知識はほとんどない〜多少ある程度で構いません。**Databricks Free Edition** で実施し、すべての出力は固定スキーマ `workspace.de_workshop` に書き込みます。
> 本講座はインストラクター主導です。独習用のマニュアルではありません。

### 概要

- **Lab 1 — SDP パイプラインを手で組む**: **Python** でストリーミングテーブルを、**SQL** でマテリアライズドビューを作成し、最初から 3 つのデータ品質エクスペクテーションを組み込みます。参照ファイルは [`labs/01-SDP/`](./labs/01-SDP/)。
- **Lab 2 — データエンジニアとして Genie Code を使う**: 1 つの Genie Code プロンプトから、すべて **SQL** のパイプライン（AutoCDC + Auto Loader + 結合 gold MV）を生成します。実行前に自分でレビューします。参照ファイルは [`labs/02-GenieCode/`](./labs/02-GenieCode/)。
- **Lab 3 — SDP のリアルタイムモード** *(任意)*: リアルタイムモード (RTM) で動く連続実行パイプラインをデプロイし、サブ秒レイテンシの集計がドライバコンソールに流れる様子を確認し、ドライバログからエンジンのレイテンシを読み取ります。参照バンドルは [`labs/03-SDP-RTM/`](./labs/03-SDP-RTM/)。

## 重要 — 使用するカタログ / スキーマ（固定）

本ワークショップは **Databricks Free Edition** での単独実行を前提とします。複数人で共有する Vocareum 環境ではないため、ユーザーごとの USER_ID は使わず、カタログとスキーマを**固定値**として使います。ガイド中のコピー & ペーストはそのまま実行できます。

- **カタログ**: `workspace`（Free Edition の既定カタログ）
- **スキーマ**: `de_workshop`
- すべての出力の書き込み先は `workspace.de_workshop` です。

スキーマと Lab 2 用のランディングデータは、下記「初回セットアップ」で作成します。

## 前提条件（Free Edition）

- 完全にサーバーレスで動作する。
- `samples.bakehouse.*` と `samples.wanderbricks.*`（公開サンプルデータ）を読み取れる。

### 使用する固定値

本ガイドのコピーブロックは以下の固定値を前提とします（置き換え不要）。

| 項目 | 値 |
|---|---|
| カタログ | `workspace`（Free Edition の既定） |
| スキーマ | `de_workshop`（出力先は `workspace.de_workshop`） |
| ランディング Volume | `workspace.de_workshop.landing`（Lab 2 の不正マーカー置き場） |

## 初回セットアップ

開始時に一度だけ、(1) ワークショップリポジトリのクローン、(2) セットアップノートブックの実行、を行います。

### 1. リポジトリをクローンする

**スパースチェックアウト**を使い、`databricks-solutions/databricks-japan-bootcamp` リポジトリ全体ではなく当ワークショップのサブディレクトリだけを取得します。

1. ワークスペースのサイドバー → **Workspace** → **Create** → **Git folder**。
2. **Create Git folder** ダイアログで:
   - **Git repository URL**: `https://github.com/databricks-solutions/databricks-japan-bootcamp`
   - **Git provider**: GitHub
   - **Git folder name**: `de-workshop-repo`
   - **Sparse checkout mode** を有効化
   - **Sparse checkout path**: `databricks-data-ai-bootcamp/20260911`
3. **Create Git folder** をクリック。`databricks-data-ai-bootcamp/20260911/` サブディレクトリがワークスペースの `de-workshop-repo/` にクローンされます。

### 2. セットアップノートブックを実行する

クローンした `databricks-data-ai-bootcamp/20260911/misc/setup_workshop.py` ノートブックを開いて **Run all** します。このノートブックが以下をまとめて行います（冪等・再実行可）:

- スキーマ `workspace.de_workshop` を作成（`workspace` は Free Edition の既定カタログ）
- ボリューム `workspace.de_workshop.landing` を作成
- `booking_fraud_flags/` に Lab 2 用の不正マーカー JSON（`samples.wanderbricks.booking_updates` の 3%）を投入

ほとんどのラボフォルダは参照ファイルのみです。一部のフォルダには、以下で説明するとおり直接実行できるノートブックが含まれています。


## Lab 1 — Lakeflow SDP パイプラインとジョブを手で組む


このラボでは、エンドツーエンドの SDP パイプラインを手書きします。よく知られた Bakehouse サンプルデータセットに対して、Python で 1 つの**ストリーミングテーブル**を、SQL で 3 つのデータ品質制約を持つ**マテリアライズドビュー**を作ります。パイプラインは 1 つ、ファイルは 2 つだけです。

### Lakeflow Pipelines Editor でパイプラインをセットアップする

1 行も書き始める前に、ステップ 1a と 1b を格納するパイプラインを作成します。

1. ワークスペースのサイドバー → **New** → **ETL pipeline**。既定名 `New Pipeline <日付> <時刻>` で **Lakeflow Pipelines Editor** が開きます。

2. a. **パイプライン名を更新** エディタ上部のパイプラインアイコン横にあるパイプライン名をクリックし、`pipeline_lab1` にリネームします。

    b. エディタはホーム配下にパイプラインのルートフォルダ（`/Workspace/Users/<your-email>/New Pipeline DATE TIME`）を自動作成します。必須ではありませんが、`pipeline-lab1` のように分かりやすい名前へリネームしても構いません。

3. **カタログ / スキーマを更新** パイプライン名の右にあるカタログ / スキーマセレクタをクリックし、次の値に設定します:
   - **Default catalog**: `de_workshop`
   - **Default catalog**: `workspace`、**Default schema**: `de_workshop` を設定し、**Save** をクリック。

   ドロップダウンは、`de_workshop` スキーマが既に存在していても *"Create schema"* しか表示しないことがあります。無視して構いません。入力したリテラルはそのまま受け付けられます。


4. 既定ファイル `my_transformation.py` はすでに Python であり、下のステップ 1a も Python を使います。

### ステップ 1a — ストリーミングテーブル（Python）

コードブロック右上の**コピー**ボタンでスニペットを取得し、エディタに貼り付けます。

（もし `unexpected indent` エラーが出たら、エディタが先頭の空行を自動インデントしたのが原因です。その場合は Genie の /fix で修正してください。）

```python
from pyspark import pipelines as dp


@dp.table(
    name="sales_transactions",
    comment="Raw bakery transactions streamed from samples.bakehouse.sales_transactions",
)
def sales_transactions():
    # @dp.table 内の spark.readStream.table(...) ⇒ ストリーミングテーブル
    return spark.readStream.table("samples.bakehouse.sales_transactions")
```

**タブバー**（エディタセルの前にあるタイトル）のファイル名をクリックし、`sales_transactions.py` にリネームします。

**Run file** をクリック。DAG サイドバーにノード `sales_transactions`（約 3,333 行）が 1 つ表示されます。Run file はこの変換だけを実行し、パイプライン全体は実行しません。

### ステップ 1b — データ品質エクスペクテーション付きマテリアライズドビュー（SQL、コピー & ペースト）

アセットブラウザ（「+」記号）→ **Add → Transformation** → 名前を `sales_stats`、言語 **SQL** にして **Create**。下のブロックを貼り付けます。3 つのエクスペクテーションを組み込んだマテリアライズドビューです:

```sql
CREATE OR REFRESH MATERIALIZED VIEW sales_stats (
    --    違反はイベントログに記録されるが、行は書き込まれる。
    CONSTRAINT reasonable_avg_value
        EXPECT (avg_txn_value BETWEEN 1 AND 1000),

    --    違反行はターゲットから除外されるが、パイプラインは継続する。
    CONSTRAINT nonneg_revenue
        EXPECT (gross_revenue >= 0) ON VIOLATION DROP ROW,

    --    違反があると、制約名とともにパイプライン更新全体が中断される。
    CONSTRAINT known_product
        EXPECT (product IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Sales KPIs grouped by product, with data-quality expectations'
AS SELECT
    product,
    COUNT(*)                     AS txn_count,
    SUM(quantity)                AS units_sold,
    ROUND(SUM(totalPrice), 2)    AS gross_revenue,
    ROUND(AVG(totalPrice), 2)    AS avg_txn_value,
    COUNT(DISTINCT customerID)   AS unique_customers,
    COUNT(DISTINCT franchiseID)  AS franchises_selling
FROM sales_transactions
GROUP BY product;
```

**Run pipeline** をクリックすると、パイプライン全体が実行されます。DAG は `sales_transactions → sales_stats`（6 行、製品ごとに 1 行）を表示します。Tables の Expectations 列でデータ品質制約を確認でき、サイドパネルを開けます。

SDP の制約構文は **1 つ** — `CONSTRAINT <name> EXPECT (<predicate>)` — で、違反時の挙動は **3 種類**: *log*（既定）、*drop row*、*fail update* です。学習のため、あえて 3 つすべてを 1 つのデータセットに組み込んでいます。

パイプラインを実行すると、ストリーミングテーブルは再更新されないことに気づくかもしれません（前回すでに実行済みで、新規データは一度だけ追記されるため）。フルリフレッシュでパイプラインを実行するか、そのファイルを明示的に再実行すると、このデータが再び読み込まれる様子を確認できます。

**重要な学習ポイント**
- ストリーミングテーブルには Python を使う。
- マテリアライズドビューには SQL を使う。相対名 `sales_transactions` は、パイプラインの既定カタログ + スキーマに対して解決される。
- Python と SQL のファイルは混在できる。特別な設定は不要。
- Bakehouse サンプルデータはきれいなので、3 つのエクスペクテーションはすべて通過し、制約なし版と行数が一致する。

**この MV は増分更新か、それとも完全再計算か?**

マテリアライズドビューは、SDP プランナがクエリを増分更新として書き換えられるかどうかに応じて、*増分更新*（変更行のみ再処理）または refresh 時の*完全再計算*のいずれかになります。単純な射影・フィルタ・多くの集計は増分更新の対象になりますが、`sales_stats` が 2 回使っている `COUNT(DISTINCT …)` は、distinct の追跡を大量の状態なしには増分維持できないため、通常 **COMPLETE refresh** を強制します。

テーブルが増分化されているかどうかの詳細は Tables / Expectations を参照してください。

### ステップ 1c（任意）— Lakeflow Jobs で SDP と下流アクションを含むワークフローを作る

SDP パイプラインと下流のコンシューマーノートブックを、2 タスクのジョブにまとめます:

1. ワークスペースのサイドバー → **Jobs & Pipelines** → **Create** → **Job**。
* 名前を `workflow_lab1` にする。
2. **タスク 1**
* **Add another task type** → **ETL Pipeline** を選択
    * Task name **my_pipeline**
    * Type **Pipeline**
    * **Pipeline** に Lab 1 の `pipeline_lab1` を選択
    * Save Task
3. **タスク 2**
    * **Add task** をクリックし Notebook を選択
    * Task name: `downstream`
    * Type **Notebook**
    * path `labs/01-SDP/downstream.py`
    * **Depends on** で `pipeline` を選択
4. **Run now** をクリック。
* ジョブが実行されることを確認。パイプラインが先に走り、成功すると通知ノートブックが起動してタスクログに出力します。
* ジョブで利用可能なトリガーの種類も確認しましょう。


### Lab 1 のまとめ

わずか数行で、Bakehouse トランザクションのストリーミングテーブル取り込み、製品ごとに売上を集計するマテリアライズドビュー、そして異なる挙動を持つ 3 つのデータ品質エクスペクテーションを作りました。


同じ構成を SDP なしで書くと、ストリーミングジョブ・バッチジョブ・スケジューラの 3 つの別システムを配線し、同期し続ける必要があります。ここではそれが 1 つのパイプラインに収まり、欲しい*ターゲットテーブル*として宣言するだけで、残りはプラットフォームが受け持ちます。

下流アクションを加えたマルチステップワークフローとしてパイプラインを実行したことで、任意のジョブトリガーから呼び出せる本番運用可能なジョブが手に入りました。


![Lab 1 — Lakeflow Pipelines Editor でのパイプライン実行完了: ストリーミングテーブル sales_transactions（出力 3.3K 行）がマテリアライズドビュー sales_stats（出力 6 行、3 エクスペクテーション、100% 書き込み、0% ドロップ）へ流れる](https://raw.githubusercontent.com/databricks-solutions/databricks-japan-bootcamp/main/databricks-data-ai-bootcamp/20260911/misc/images/lab1-ui-expectations.png)



---

## Lab 2 — データエンジニアとして Genie Code を使う

Lab 1 では全行を自分でタイプしました。Lab 2 でタイプするのは*1 つ* — プロンプトだけです。Genie Code は SDP パイプライン全体を構築する AI 支援ツールです。SQL で 3 つの異なるソースから取り込み、JOIN と gold テーブルを作ります:
* `booking_updates` CDC フィードに対する AutoCDC
* 特定の予約に対する不正マーカーの JSON Volume に対する Auto Loader
* payments に対するプレーンなストリーミングテーブル

あなたはプロンプトを与え、レビューし、承認します。

このラボが教えるスキルは SQL をタイプすることではありません。*正しそうに見えて実は正しくない*ドラフトを見抜くことです。

### 新しいパイプラインをセットアップする

1. ワークスペースのサイドバー → **New** → **ETL pipeline**。`pipeline_lab2` にリネーム。エディタが同名のワークスペースフォルダをホーム配下に自動作成し、Genie Code はそこに生成した 5 つの SQL ファイルを書き込みます。
2. **Default catalog** を `workspace`、**Default schema** を `de_workshop` に設定（Lab 1 と同じ）。


### Genie Code を開く

1. ワークスペース右上 → **Genie Code** をクリック。サイドパネルが開きます。
2. Genie Code ペイン下部で、**Agent** モードセレクタが **Agent**（**Chat** ではない）になっていることを確認。
3. Genie Code がファイルを作成したりコードを実行したりするたびに承認プロンプト（Allow / Decline / Allow in this thread / Always allow）が出ます。このラボでは **絶対に** *Always allow* をクリックしないでください。各 diff をレビューすることこそが目的です。

### プロンプト

以下を Genie Code Agent に貼り付けます:

```text
build a SQL pipeline with SDP with catalog de_workshop and schema XXX that answers the question:
"Is fraud risk related to party size and payment method?"

Inputs:
1. samples.wanderbricks.booking_updates — a CDC stream of booking state-update events 
2. samples.wanderbricks.payments streaming data 
3. /Volumes/workspace/de_workshop/landing/booking_fraud_flags/with JSON files marking fraudulent bookings 

* mark all bookings with fraud in bookings_with_fraud.
* gold materialized view fraud_by_party_and_method: use bookings_with_fraud and payments 


Run the pipeline, report row counts, and answer the question about fraud and its correlation.
```

> このプロンプトは英語のままにしてください。参照 SQL と後掲の期待 DAG は、この英語プロンプトから生成されたものです。`schema` の `XXX` は `de_workshop` に置き換えてください。

このプロンプトはあえて高レベルにしてあります。*ビジネス上の問い*と*入力*だけを述べ、解法（テーブル名、列、結合の形、集計の形）は Genie Code に計画させます。これが AI データエンジニアリングエージェントの正しい使い方です。

### 検証 — 最も重要なステップ

プロンプトが高レベルなので、Genie Code には選択の余地があります。**解が少し違って見えても心配ありません。Genie Code は継続的に改善されています。**

提案された各ファイルで **Allow** をクリックする前に、下の参照 SQL と照合してください。良い生成が満たすべき性質:

- `bronze/bookings.sql` は `samples.wanderbricks.booking_updates` に対して **AutoCDC** パターンを使う
- `bronze/fraud_flags.sql` は JSON Volume に対して `STREAM(read_files(...))` の Auto Loader を使う
- `bronze/payments.sql` は Delta ソースに対するプレーンなストリーム
- `silver/bookings_with_fraud.sql` は bookings と不正フラグを結合するマテリアライズドビュー

- gold テーブルは 3 つの入力ソースすべてのデータを結合する

なお、SCD Type 1 の AutoCDC は「スクラップブック」ではなく「タイムラプス」です。すべての更新は `booking_id` ごとに 1 つの現在行へ収束します。最新の状態が勝ち、履歴は消えていきます。

**`SCD TYPE 1` と `SCD TYPE 2`。** Type 1 は `booking_id` ごとに現在行だけを保持します。更新はその場で上書きされ、履歴は残りません。Type 2 は `__START_AT` / `__END_AT` 列とともにすべての履歴バージョンを保持するため、過去の*時点*でのクエリができます。このラボは、gold の問いが現在状態を尋ねているため Type 1 を使います。

### Genie Code に Chat モードで尋ねる

Genie Code を **Chat** モードに切り替え、次を尋ねます:

```text
Explain the data flow in this pipeline end-to-end. Which node is incrementally maintained versus fully recomputed on refresh, and why?
```

### 期待される表示

![Lab 2 — Genie Code が生成した、bronze（bookings, fraud_flags, payments）、silver（bookings_with_fraud）、gold（fraud_by_party_and_method）レイヤーを持つパイプライン（Lakeflow Pipelines Editor）](https://raw.githubusercontent.com/databricks-solutions/databricks-japan-bootcamp/main/databricks-data-ai-bootcamp/20260911/misc/images/lab2-dag.png)

Lakeflow Pipelines Editor は、右に Genie Code の計画、中央に生成された SQL、下に行数付きの解決済み DAG を表示します。3 つの bronze ストリーミングテーブル、1 つの silver ストリーミングテーブル、1 つの gold マテリアライズドビューです。行数を[検証](#検証--最も重要なステップ)セクションと照合するサニティチェックに使ってください。

---

## Lab 3 — SDP のリアルタイムモード（任意）

> **任意。** 時間が足りなければスキップして構いません。ワークショップの他の部分はこれに依存しません。デモ全体は 1 つの `databricks.yml` を Workspace UI からデプロイするだけです。

標準の SDP はマイクロバッチとして動きます。新しい**リアルタイムモード (RTM)** は、長時間実行バッチ・ステージの同時スケジューリング・ストリーミングシャッフルを組み合わせ、エンドツーエンドのレイテンシをミリ秒レンジまで押し下げます。このラボでは、SDP パイプラインで **RTM を有効化する方法** — 必要な 3 つの設定ステップ — を、Workspace UI からデプロイしながら示します。

**パブリックプレビュー:** 現在、Lakeflow SDP の RTM には SDP の **PREVIEW** チャンネルが必要です。

*このラボは、パイプラインコードで使う構文を含む最新アップデートがロールアウト済み（2026 年 5 月末）であることを前提とします。*

### RTM を有効化する 3 つの設定ステップ

1. パイプラインレベルの **Continuous モード**。
2. パイプラインの Spark 設定での **`spark.databricks.streaming.realTimeMode.enabled = true`**。
3. `pipelines.trigger: "RealTime"` を持つ **`@dp.update_flow`**（`@dp.table` / `@dp.view` ではない）。

これから deploy するバンドルには、この 3 つがすでにすべて配線されています。

### deploy するもの

1 ファイルの最小パイプライン: 合成 `rate` ソース、スライディングウィンドウ集計（10 秒ウィンドウ、2 秒スライド）、そしてウィンドウ化された行がドライバログに着地する `console` シンク。

### ステップ 3a — RTM バンドルを開く

ワークショップ開始時にすでにリポジトリをクローン済みです。`labs/03-SDP-RTM/` サブディレクトリに移動してください。deploy 可能な `databricks.yml` と `sdp-rtm-rate-source/transformations/temperature_rtm.py` が用意されています。

### ステップ 3b — バンドルを自分のスキーマ向けに調整する

`labs/03-SDP-RTM/databricks.yml` を開きます。deploy を駆動する変数は 2 つです。自分の値に設定してください:

```yaml
variables:
  catalog_name:
    default: workspace         # Free Edition の既定カタログ
  schema_name:
    default: de_workshop       # 固定スキーマ（workspace.de_workshop）
```

`continuous: true`、`serverless: true`、`channel: PREVIEW`、および RTM 有効化フラグはすでに設定済みです。そのままにしてください。パイプラインの `root_path` は `./sdp-rtm-rate-source` に設定されており、Lakeflow Pipelines Editor はそのサブフォルダをプロジェクトツリーのルートとして扱います。

フローファイル `sdp-rtm-rate-source/transformations/temperature_rtm.py` が実際の RTM パイプラインです。`pipelines.trigger: "RealTime"` を持つ `@dp.update_flow` デコレータ、合成 `rate` ソース、ウィンドウ集計に注目してください:

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import avg, col, count, expr, max as max_, min as min_, window

dp.create_sink(
    "hot_temperatures_sink",
    "console",
    {"mode": "append", "truncate": "false"},
)


@dp.update_flow(
    name="temperature_rtm_flow",
    target="hot_temperatures_sink",
    spark_conf={
        "pipelines.trigger": "RealTime",
        "pipelines.trigger.interval": "2 minutes",
    },
)
def temperature_rtm_flow():
    return (
        spark.readStream
        .format("rate")
        .option("rowsPerSecond", "100")
        .load()
        .withColumnRenamed("timestamp", "source_timestamp")
        .withColumn("temperature_c", expr("19 + rand() * 7"))
        .withWatermark("source_timestamp", "10 seconds")
        .groupBy(window(col("source_timestamp"), "10 seconds", "2 seconds"))
        .agg(
            count("*").alias("event_count"),
            avg("temperature_c").alias("avg_temp_c"),
            min_("temperature_c").alias("min_temp_c"),
            max_("temperature_c").alias("max_temp_c"),
        )
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("event_count"),
            col("avg_temp_c"),
            col("min_temp_c"),
            col("max_temp_c"),
        )
    )
```


### ステップ 3c — Workspace UI から deploy して実行する

1. ワークスペースで `labs/03-SDP-RTM/` フォルダを開きます。`databricks.yml` があるため、左ペインに **Deployments** アイコン（🚀）が現れます。
2. **Deployments** をクリック → **`prod`** ターゲット（このバンドルで定義された唯一のもの）を選択 → **Deploy**。
3. 検証と deploy が終わったら、deploy 済みの `sdp-rtm-rate-source` パイプラインを開きます。**注意:** パイプラインは `continuous: true` なので、deploy 時点で最初の更新が自動開始しています。クリックするものはありません。

もし **Run** をクリックしても既に実行中の場合、*"An active update already exists for pipeline …"* と表示されることがあります。これは想定内です。既存の更新をそのまま実行させておいてください。

### ステップ 3d — パイプライン出力を確認する

ドライバログを開いて、パイプラインが出力を生成していることを確認します:

1. Lakeflow Pipelines Editor で `sdp-rtm-rate-source` パイプラインを開いた状態で、上部の **Compute** をクリック。
2. compute ペインで **Driver logs** をクリック。

**Console シンクのバッチテーブル — ウィンドウ集計がシンクに着地する様子。** データが RTM フローを流れていることの視覚的な確認です:

```
+--------------------+--------------------+-----------+------------------+------------------+------------------+
|window_start        |window_end          |event_count|avg_temp_c        |min_temp_c        |max_temp_c        |
+--------------------+--------------------+-----------+------------------+------------------+------------------+
|2026-05-15 09:42:18 |2026-05-15 09:42:28 |1000       |22.51             |19.00             |25.99             |
```


* [RTM のレイテンシ](https://docs.databricks.com/aws/en/structured-streaming/stream-monitoring)を表示するために `StreamingQueryListener` を登録することもできます。
* あるいは、log4j 出力で `e2eLatencyMs` という部分文字列を含むエントリを確認します。各エントリは、パイプラインの 3 ステージについてレコードごとのレイテンシパーセンタイル（P0/P50/P90/P95/P99）を報告します:

```json
"latencies" : {
    "processingLatencyMs" : {
      "P0" : 1.0,
      "P50" : 27.0,
      "P90" : 48.0,
      "P95" : 50.0,
      "P99" : 54.0
    },
    "sourceQueuingLatencyMs" : {
      "P0" : 0.0,
      "P50" : 0.0,
      "P90" : 0.0,
      "P95" : 1.0,
      "P99" : 6.0
    },
    "e2eLatencyMs" : {
      "P0" : 1.0,
      "P50" : 27.0,
      "P90" : 48.0,
      "P95" : 50.0,
      "P99" : 62.0
    }
  }
```

`e2eLatencyMs` は `sourceQueuingLatencyMs`（レコードがソースで待機した時間）+ `processingLatencyMs`（エンジンが処理に費やした時間）の合計です。これらのメトリクスは RTM でのみ出力されます。

### ステップ 3e — 終わったらパイプラインを停止して削除する

パイプラインは**連続実行かつサーバーレス**なので、停止するまでコンピュートを消費し続けます。レイテンシの観察が終わったら必ず停止してください:

- Lakeflow Pipelines Editor でパイプラインを開いた状態で上部の **Stop** をクリック、**または**
- deploy に使ったロケット記号の同じ UI からデプロイを削除する。


---

## 参考資料とその他のデモ

* [Get to know Genie Code: Lakeflow and Analytics](https://www.databricks.com/resources/demos/videos/get-know-genie-code)
* 完全版 [Lakeflow Demo: From messy sales data to AI insights](https://www.databricks.com/resources/demos/videos/lakeflow-action-gourmet-pipeline-demo-daiwt)
* 見ておきたい RTM デモ: [Air Traffic Control with Apache Spark Structured Streaming — Real-Time Mode](https://www.databricks.com/resources/demos/videos/air-traffic-control-with-apache-spark-structured-streaming-real-time-mode)
* 次回のデータエンジニアリングワークショップや、DBSQL・AI・Unity Catalog 向けの[その他の Databricks ワークショップ](https://www.databricks.com/events?event_type=workshop&region=all)を探す
