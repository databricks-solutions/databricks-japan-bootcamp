# Lakeflow Designer ハンズオン プロンプト集

> Databricks Data + AI Bootcamp 大阪 後半パート（名寄せシナリオ）
> Lakeflow Designer の各演算子で Genie Code に入力するプロンプトをまとめたもの。
> スライド 194〜228 の内容と対応。
>
> **基本姿勢**: 演算子はドラッグで配置 → 中身の設定は以下のプロンプトを Genie Code に入力。

---

## 環境情報

| 項目 | 値 |
|---|---|
| カタログ | `workspace`（Free Edition）|
| スキーマ | `bootcamp_tokyo` |
| 入力テーブル | `dirty_companies`（3,856 行）/ `master_companies`（25 行）|
| 出力テーブル | `gold_company_sales` |

> ⚠️ **スライド要修正**: 一部スライドのカタログ名が不統一です（後述の「スライド修正メモ」参照）。

---

## Step 1. Source 配置（プロンプト不要）

ドラッグで Source 演算子を 2 つ配置し、UI で選択:

| Source | カタログ | スキーマ | テーブル |
|---|---|---|---|
| 1 | `workspace` | `bootcamp_tokyo` | `dirty_companies` |
| 2 | `workspace` | `bootcamp_tokyo` | `master_companies` |

---

## Step 2-1. 類似度比較（AI 関数）

> スライド 195。`dirty_companies` の横の ＋ボタン → AI 関数を選択 → 以下を入力。

```
やること: company_name と master_companies.official_name で文字列類似度を計算し、
各 company_name に対して最も似ている official_name を上位 3 件取得して
similar_candidates 列（配列）に出力する。

クレンジングも内包:
- company_name が "", "(不明)", "-", "N/A", "未設定" の行は処理対象外
- company_name の前後の空白・タブ・改行は比較時にトリムする

出力列（この列構成で必ず出力すること）:
- transaction_id (string)
- company_name (string)
- transaction_date (date)
- amount (bigint)
- similar_candidates (array<string>) ← 新規追加
```

> 処理中表示が消えたら「すべて承認」を押す。

---

## Step 2-2. AI カスタムプロンプトで名寄せ判定

> スライド 199。一番右のオペレーターの ＋ボタン → AI 関数を選択 → 以下を入力。

```
やること: company_name と similar_candidates から AI に同一企業を判定させ、
正式名称を matched_name 列に出力する。

モデル: databricks-meta-llama-3-3-70b-instruct
出力列名: matched_name

プロンプト本文:
取引先名「{{company_name}}」に対して、候補マスタ {{similar_candidates}} の中から
最も同一企業と判定される正式名称を 1 つだけ選び、その文字列のみを出力してください。

判定ルール:
- company_name が空欄、"(不明)", "-", "N/A", "未設定" のいずれかの場合は "null" のみ
- company_name の前後の空白・タブは無視して本体だけで判定
- 略称・カタカナ表記・英字表記は同一企業扱い
- 末尾の担当者名・部署名・メモ・業界追記は無視
- "旧" プレフィックスも無視して本体名で判定
- 候補のいずれも明らかに別企業の場合は "null" のみ

出力は文字列のみ。説明文・JSON・引用符などは付けない。

出力列（この列構成で必ず出力すること）:
- transaction_id (string)
- company_name (string)
- transaction_date (date)
- amount (bigint)
- similar_candidates (array<string>)
- matched_name (string) ← 新規追加（AI の出力）
```

---

## Step 3-1. master テーブルと Join

> スライド 201。＋ボタン → 結合を選択 → ダブルクリックで直前のオペレーターと `master_companies` を選択 → 以下を入力。

```
やること: matched_name (左) = official_name (右) で INNER JOIN する。

注意:
- 結合後の列名に left./right. の接頭辞は付けない
- matched_name が "null" の行は INNER JOIN で自然に除外される

出力列（この列構成で必ず出力すること）:
- master_id (string) ← master 側から
- official_name (string) ← master 側から
- industry (string) ← master 側から
- transaction_date (date) ← 左側から
- amount (bigint) ← 左側から
```

---

## Step 3-2. Aggregate で月次集計

> スライド 203。＋ボタン → 集計を選択 → 以下を入力。

```
やること: 取引データを月次集計する。
- transaction_date から年月を取り出して year_month 列を作る（"YYYY-MM" 形式）
- master_id, official_name, year_month の 3 つでグループ化
- amount の合計を monthly_revenue 列に出力

列参照に left./right. の接頭辞は使わない。

出力列（この列構成で必ず出力すること）:
- master_id (string)
- official_name (string)
- year_month (string) ← "YYYY-MM"
- monthly_revenue (bigint) ← SUM(amount)
```

---

## Step 3-3. Window 関数でランキング順位

> スライド 205。＋ボタン → 集計を選択 → 以下を入力。

```
やること: 月別ランキング順位を付ける。
- パーティション: year_month
- 並び順: monthly_revenue 降順
- 順位列名: rank_in_month
- ランキング関数: ROW_NUMBER

出力列（この列構成で必ず出力すること）:
- master_id (string)
- official_name (string)
- year_month (string)
- monthly_revenue (bigint)
- rank_in_month (int) ← 新規追加
```

---

## Step 4. Output で集計テーブル書き込み

> スライド 207。＋ボタン → 出力を選択 → 以下を入力。

```
やること: workspace.bootcamp_tokyo.gold_company_sales に
このテーブルを書き出す（CREATE OR REPLACE で上書き）。

書き出す列（これが含まれていること）:
- master_id (string)
- official_name (string)
- year_month (string)
- monthly_revenue (bigint)
- rank_in_month (int)
```

> ✏️ **スライド 207 のカタログ名が `bootcamp_tokyo_v21_catalog`（タイポ）**になっています。Free Edition なら `workspace` に修正してください。

---

## Step 5. メトリクスビューの作成

> スライド 211。カタログエクスプローラーで `gold_company_sales` を開く →
> 作成 → メトリクスビュー → ランプのマーク（AI アシスタント）に以下を入力。

```
現在表示しているメトリクスビューを作成してください。条件は以下で YAML を生成する。

ディメンション:
- official_name : 取引先名（そのまま）
- year_month : 年月（そのまま、"YYYY-MM" 形式）
- year : 年（year_month の先頭 4 文字）
- customer_tier : 顧客ランク（CASE WHEN で 3 段階）
    - monthly_revenue >= 5000000 → 'A:重要取引先'
    - monthly_revenue >= 1000000 → 'B:中堅'
    - その他 → 'C:その他'

メジャー:
- revenue : 売上合計（SUM(monthly_revenue)）
- customer_count : 取引先数（COUNT DISTINCT master_id）
- important_customer_count : 重要取引先数（月次売上 500 万円以上の取引先数）
- important_customer_revenue : 重要取引先売上（A ランク取引先の売上合計）

各メジャー・ディメンションに description（日本語の業務説明）を必ず付けること。
description には日本語の業務用語（"重要取引先" "A ランク" 等）を明示すること
（Genie が日本語の質問とメジャーを紐付けるのに使う）。
```

---

## Step 6. Genie で問い合わせ（MV 有無の比較）

> スライド 215 / 219。Genie Space を作成し、以下の質問を投げる。

### 比較する質問
```
重要取引先は何社?
```
```
A ランクの取引先一覧を教えて
```

### 比較ポイント（スライド 216・220）
| データソース | 「重要取引先は何社?」の回答 |
|---|---|
| `gold_company_sales`（MV なし） | "重要"の定義がないため **25 社**（全件）と返りがち |
| `gold_company_sales_metric_view`（MV あり） | MV で「重要取引先 = 月次売上 500 万円以上」と定義済みのため **正確な社数** |

→ メトリクスビューに業務定義を埋め込むことで、同じ質問でも回答が変わる。

---

# Appendix

## A1. AI チャットに一発でパイプラインを生成させる

> スライド 221 / 228。Designer の Genie Code に以下を一発入力。

```
2 つのテーブルを使って、取引先別の月次売上ランキングを作るパイプラインを組んでください。
@dirty_companies は各部署が入力した取引データで、取引先名（company_name）の表記がバラバラです。
@master_companies が正式マスタです。
以下の処理を行ってください:
1. dirty_companies の company_name の前後空白を除去
2. AI を使って dirty_companies の各行に最も近い master_companies の official_name を判定し、master_id を付与
3. 取引先 × 年月 で月次売上を集計し、月別のランキング順位を付与
出力テーブルの列: master_id, official_name, year_month, monthly_revenue, rank_in_month
```

## A2. 画像（Excel スクショ）でパイプラインを生成させる

> スライド 225。`material/ideal_ranking_2026_03.xlsx` のスクショを Genie Code に貼り付け → 以下を入力。

```
やること: 画像のテーブル形式に合わせて取引先別売上ランキングを出力する。
入力テーブル:
- workspace.bootcamp_tokyo.gold_company_sales
- workspace.bootcamp_tokyo.master_companies (業界取得用)
出力する列（画像のヘッダーに合わせる）:
- 順位（rank_in_month）
- 取引先名（official_name）
- 業界（master_companies の industry を JOIN）
- 月次売上（monthly_revenue）
フィルタ: year_month = '2026-03'
並び順: monthly_revenue 降順
行数: Top 20
```

> ✏️ **スライド 225 のカタログ名が `bootcamp_osaka_v21_catalog`** になっています。
> Free Edition なら `workspace` に修正してください。

---

# スライド修正履歴（2026-05 反映済み）

本番は **Free Edition（`workspace` カタログ）**。以下のスライド修正を反映済み:

| スライド | 修正前 | 修正後 | 状態 |
|---|---|---|---|
| 207 | `bootcamp_tokyo_v21_catalog`.bootcamp_tokyo.gold_company_sales | `workspace`.bootcamp_tokyo.gold_company_sales | ✅ 反映済 |
| 225 | `bootcamp_osaka_v21_catalog`.bootcamp_tokyo.* | `workspace`.bootcamp_tokyo.* | ✅ 反映済 |
| 224 | ボリューム名 `bootcamo_csv`（タイポ） | `bootcamp_csv` | ✅ 反映済 |
| 221 / 228 | `@transactions` 参照（3 テーブル） | dirty_companies + master の 2 テーブル構成 | ✅ 反映済 |

> Source 選択スライド（185-192）は元から `workspace.bootcamp_tokyo` を指しており正しい。
