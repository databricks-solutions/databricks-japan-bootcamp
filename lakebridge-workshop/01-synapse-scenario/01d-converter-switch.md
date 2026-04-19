# 01d. Converter: Switch (Synapse)

Switch は LLM ベース (Foundation Model API / Claude Sonnet) のトランスパイラ。**ルールベースで詰まる複雑ストアド**に強く、任意の source dialect に対応できる柔軟性が売り。Databricks Job として動作するため、ローカル CLI ではなくワークスペース上で実行する。

## 実行 (Databricks Workspace 上)

### 1. Switch Job をワークスペースにインストール

```bash
databricks labs lakebridge install-transpile --profile DEFAULT
```

`install-transpile` のプロンプトで **Switch** を選択すると、ワークスペースに以下が展開される。

- Job: `Switch_{ランダムサフィックス}`
- ノートブック / ライブラリ一式

> 既に `00-prereq.md` で `All` を選んでインストール済なら Switch も入っている。`databricks labs lakebridge describe-transpile` に `name: Switch` が含まれているか確認。

### 2. インプットをワークスペースの Volume にアップロード

```bash
# 例: Unity Catalog Volume を用意 (未作成なら)
databricks sql-queries create \
  --query "CREATE VOLUME IF NOT EXISTS main.default.lakebridge_input" \
  --warehouse-id <your-warehouse-id>

# 手元の input をアップロード
databricks fs cp -r ./input \
  dbfs:/Volumes/main/default/lakebridge_input/synapse
```

> Volumes 名・catalog/schema は自分のワークスペース環境に合わせる。

### 3. Switch Job を起動

Databricks Workspace UI を開き、**Workflows → Jobs** で `Switch_...` を探す。`Run now with different parameters` から以下を指定:

| パラメータ | 値の例 |
|---|---|
| `input_dir` | `/Volumes/main/default/lakebridge_input/synapse` |
| `output_dir` | `/Volumes/main/default/lakebridge_output/synapse` |
| `source_tech` | `tsql` (または `synapse`) |
| `foundation_model` | `databricks-claude-sonnet-4` (ワークスペース既定のもの) |
| `concurrency` | `4` 程度 |

実行し、完了まで 3〜5 分待つ (ファイル数 × LLM 呼び出しのため、DDL + ストアド 7 本で数分)。

### 4. 生成物を確認

Workspace UI の `output_dir` 配下に変換後 SQL + コメントが生成されている。

- 特に `mssql_example2_stored_procedure.sql`: 動的 SQL / TRY-CATCH / sp_executesql が**意味的に等価な Databricks SQL + Python** で再構築されているかを観察
- 行単位コメントで「元の何行目の何を変換したか」が入っているのが Switch の特徴

### 学習ポイント

- **Switch の強み**: LLM が構文の意図を読んで書き直すため、ルールベースでは詰まる複雑ストアドでも 1 発変換を狙える
- **Switch の弱み**: LLM 呼び出しコスト、非決定性 (再実行で微妙に差分)、レビュー必須
- **使い分けの勘所**:
  - Analyzer レポートの `llm_support_needed = true` のファイル
  - DDL や定型 SQL はルールベース、複雑ストアドだけ Switch に回す
- プロンプトの工夫余地: Switch Job のパラメータで `custom_instructions` を渡してスタイル統一できる (応用編、今回は触れない)

## BladeBridge / Morpheus との比較

3 つの出力を並べて見ると:

| 観点 | BladeBridge | Morpheus | Switch |
|---|---|---|---|
| DDL 5 本 | 十分変換 | 十分変換 | 変換できるがオーバースペック |
| ストアド example1 | 大半 OK | 大半 OK | OK + 意図コメント |
| ストアド example2 (複雑) | 部分変換 | 部分変換 | **フル変換を狙える** |
| 決定性 | 高 | 高 | 中 (再実行で差分) |
| コスト | 低 | 低 | 中 (LLM 呼出) |

これが**使い分けの腹落ちポイント**。

## 次

[Lab 2: Reconciler](../02-reconciler/02-reconciler.md) へ。
