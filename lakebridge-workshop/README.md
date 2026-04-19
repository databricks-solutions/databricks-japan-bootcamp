# Lakebridge Workshop for Partner Champions

**開催日**: 2026-04-22 (水) 13:30-19:00
**担当セッション**: 14:40-16:20 ハンズオン (90 分) + 16:30-17:00 AMA
**対象**: Databricks Japan Partner SA Champion
**講師**: 中里 (Databricks Japan DSA)

## 本ワークショップのゴール

Lakebridge (Analyzer / Converter / Reconciler) と Switch を**実際に手を動かして動かす**ことで、自社でマイグレーション案件を提案・推進できる状態になる。

## 前提

[00-prereq.md](00-prereq.md) を参照。ワークスペース要件、CLI インストール、Lakebridge install、プロファイル設定、Switch Job インストールを 10-15 分で済ませる。

## タイムボックス (90 分)

| 時間 | セクション | 内容 |
|---|---|---|
| 0-5 min | イントロ | 全体流れ + 前提最終確認 |
| 5-18 min | [01a Analyzer](01-synapse-scenario/01a-analyzer.md) | Synapse DDL + ストアドを解析 |
| 18-28 min | [01b BladeBridge](01-synapse-scenario/01b-converter-bladebridge.md) | 同 input を BladeBridge で変換 |
| 28-38 min | [01c Morpheus](01-synapse-scenario/01c-converter-morpheus.md) | 同 input を Morpheus で変換、BladeBridge と diff |
| 38-55 min | [01d Switch](01-synapse-scenario/01d-converter-switch.md) | 同 input を Switch で変換、複雑ストアドでの強み |
| 55-70 min | [Lab 2 Reconciler](02-reconciler/02-reconciler.md) | Databricks 内 2 テーブル比較 (独立 Lab) |
| 70-88 min | [シナリオ 3 DataStage](03-datastage-scenario/README.md) (オプション) | Analyzer + BladeBridge → PySpark Notebook |
| 88-90 min | バッファ | 押しを吸収、AMA へ繋ぐ |

### 時間押し対応の優先順位

時間が足りなくなった場合、以下の順で削る:

1. **シナリオ 3 全体** (オプション)
2. `01c Morpheus` (BladeBridge との比較を口頭で補う)
3. `01b BladeBridge`

**Switch と Reconciler は必ず残す** — 本ワークショップのコア。

## ディレクトリ構成

```
lakebridge-workshop/
├── README.md                         # 本ファイル
├── 00-prereq.md                      # 前提セットアップ
├── 01-synapse-scenario/              # シナリオ 1: Synapse / T-SQL
│   ├── README.md
│   ├── input/
│   │   ├── ddl/                      # 自作 Synapse DDL 5 本
│   │   └── stored_procs/             # Switch 公開サンプル 2 本
│   ├── 01a-analyzer.md
│   ├── 01b-converter-bladebridge.md
│   ├── 01c-converter-morpheus.md
│   └── 01d-converter-switch.md
├── 02-reconciler/                    # Lab 2: Reconciler (独立)
│   ├── README.md
│   ├── setup.sql                     # Databricks 内 2 テーブル + 差分 5 行
│   ├── config/recon_config.yaml
│   └── 02-reconciler.md
└── 03-datastage-scenario/            # シナリオ 3: DataStage (オプション)
    ├── README.md
    ├── input/xml/                    # 無毒化済 DataStage XML 2 本
    ├── 03a-analyzer.md
    └── 03b-converter-bladebridge.md
```

## Lakebridge / Switch の使い分け早見表

| 対象 | 推奨 Converter | 理由 |
|---|---|---|
| DDL (テーブル定義) | BladeBridge / Morpheus | ルールベースで決定論的・低コスト |
| 定型 SQL (単純 SELECT / UPDATE) | BladeBridge / Morpheus | 同上 |
| 複雑ストアド (動的 SQL / TRY-CATCH / sp_executesql) | **Switch (LLM)** | 意味的に等価な書き換えが必要 |
| DataStage / Informatica / SSIS (XML メタデータ) | **BladeBridge** | 対応している唯一の Lakebridge transpiler |
| mssql / snowflake / synapse の SQL | Morpheus (Databricks 純正) 優先、ダメなら BladeBridge | 純正ゆえ追従速度が速い |

Analyzer の `llm_support_needed = true` フラグが Switch を充てる根拠になる。

## トラブルシュート

### `transpile` コマンドが `EOFError` で落ちる

非インタラクティブ環境 (CI など) で `Select the transpiler:` プロンプトが待てずに落ちる。明示的に config-path を指定する。

```bash
# BladeBridge
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml

# Morpheus
--transpiler-config-path ~/.databricks/labs/remorph-transpilers/databricks-morph-plugin/lib/config.yml
```

### `databricks labs lakebridge describe-transpile` に Morpheus が出ない

`install-transpile` 実行時に `All` を選んでいない可能性。再度:

```bash
databricks labs lakebridge install-transpile --profile DEFAULT
```

### Switch Job が Foundation Model で失敗する

ワークスペースで `databricks-claude-sonnet-4` エンドポイントへの `Can Query` 権限を確認。権限が無ければワークスペース管理者に付与依頼。

### Reconciler のレポートテーブルが見つからない

`configure-reconcile` で指定した metadata catalog/schema を `databricks labs lakebridge configure-reconcile --profile DEFAULT` で再確認。既定は `remorph_reconcile`。

## 参考

- Lakebridge 公式: https://databrickslabs.github.io/lakebridge/
- Switch 公式: https://github.com/databricks-solutions/switch
- `databricks labs lakebridge describe-transpile` で利用可能な transpiler と dialect を常に確認できる
