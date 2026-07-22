# コーディングエージェント併用ハンズオン (Teradata)

Teradata SQL を BladeBridge で変換し、残った構文をコーディングエージェントに分析させ、BladeBridge override として変換ルールに追加する。

このハンズオンで覚えることは一つだけ。

> **変換後 SQL を直接直すのではなく、変換ルールを直して最初から再生成する。**

> **前提**: 共通セットアップ ([SETUP.md](../SETUP.md)) を完了し、Claude Code / Codex などのコーディングエージェントを利用できること。

## 60分で行うこと

```text
Teradata SQL
    ↓
BladeBridge 標準変換
    ↓
チェッカーで残った構文を確認
    ↓
エージェントが override を追加
    ↓
同じ入力から再変換
    ↓
チェッカーで改善を確認
```

今回は、このループを一度最後まで回す。BTEQ、ストアドプロシージャの再設計、結果データの一致検証までは扱わない。

## 使用するファイル

| パス | 用途 |
|---|---|
| `input/01_identity.sql` | `NO CYCLE` を含む Teradata の IDENTITY 列 |
| `input/02_update_from.sql` | Teradata の `UPDATE ... FROM` |
| `overrides/teradata-overrides.json` | 参加者がエージェントと育てる override |
| `tools/prepare_overrides.py` | override 内のベース設定をローカル絶対パスへ展開 |
| `tools/check_sql.py` | SQL Warehouse の `EXPLAIN` を使った構文チェック |
| `_reference_output/before/` | BladeBridge 標準変換の出力例 |
| `_reference_output/solution/` | override 適用後の出力例と完成 override |
| `out/` | 参加者が生成する出力。Git 管理外 |

## 1. 標準変換する

```bash
cd lakebridge-workshop/coding-agent/
mkdir -p out

databricks labs lakebridge transpile \
  --source-dialect teradata \
  --input-source ./input \
  --output-folder ./out/before \
  --skip-validation true \
  --transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml \
  --profile <your-profile>
```

`--skip-validation true` は、生の変換結果を出力し、この後のチェッカーで同じ条件の検証を行うために指定する。

## 2. 残った構文を確認する

```bash
python3 tools/check_sql.py out/before --profile <your-profile>
```

Lakebridge v0.14.0 での出力例では、次の2か所が残る。

| 入力 | 標準変換後に残るもの |
|---|---|
| `01_identity.sql` | Databricks SQLで利用できない `NO CYCLE` |
| `02_update_from.sql` | Teradata形式の `UPDATE ... FROM` |

期待結果は `FAIL 2`。バージョンにより変換結果や件数が変わる場合は、件数ではなく実際の出力を確認する。

この時点の例は [`_reference_output/before/`](_reference_output/before/) にある。

## 3. エージェントに変換ルールを作らせる

エージェントには、変換後SQLの手修正ではなく、再利用できるoverrideの作成を依頼する。

次のプロンプトを渡す前に、`<your-profile>` を自分の Databricks CLI プロファイル名へ置き換える。

```text
input/ は Teradata SQL、out/before/ は BladeBridge の標準変換結果です。

python3 tools/check_sql.py out/before --profile <your-profile>

の失敗を分析し、同じ input/ から構文チェックを通る SQL を再生成できるように、
overrides/teradata-overrides.json に BladeBridge override を実装してください。

- out/before/ の SQL を直接編集しないこと
- input/ の意味を変えないこと
- inherit_from の __BLADEBRIDGE_BASE_CONFIG__ は変更しないこと
- 適用範囲が広すぎる正規表現を避けること
- 再変換と検証は README.md の「4. override付きで再変換する」を参照すること
- 変更後の再変換コマンドと検証コマンドを示すこと
```

完成例は [`_reference_output/solution/teradata-overrides.json`](_reference_output/solution/teradata-overrides.json) にある。まずエージェントに作らせてから比較する。

時間内に完成しない場合は、次のコマンドで完成例を使い、再変換と検証まで進める。

```bash
cp _reference_output/solution/teradata-overrides.json overrides/teradata-overrides.json
```

## 4. override付きで再変換する

BladeBridge の `inherit_from` と `--overrides-file` はローカル環境の絶対パスを必要とする。テンプレートを直接環境依存にせず、実行用ファイルを `out/` に生成する。`$(pwd)` は、生成した override を絶対パスで BladeBridge に渡すために使う。

```bash
python3 tools/prepare_overrides.py \
  overrides/teradata-overrides.json \
  out/teradata-overrides.json

databricks labs lakebridge transpile \
  --source-dialect teradata \
  --input-source ./input \
  --output-folder ./out/solution \
  --skip-validation true \
  --transpiler-config-path ~/.databricks/labs/remorph-transpilers/bladebridge/lib/config.yml \
  --overrides-file "$(pwd)/out/teradata-overrides.json" \
  --profile <your-profile>

python3 tools/check_sql.py out/solution --profile <your-profile>
```

期待結果は `FAIL 0`。

- `NO CYCLE` が削除される
- `UPDATE ... FROM` が `MERGE INTO` に変換される
- `out/before/` は手で修正していない
- 同じ入力とoverrideから、結果を再生成できる

完成したSQLの例は [`_reference_output/solution/`](_reference_output/solution/) にある。

## 5. 何が改善されたか説明する

最後に、次を自分の言葉で説明できれば、このハンズオンのゴールは達成。

1. BladeBridgeの標準変換だけでは、何が残ったか
2. エージェントは最終SQLではなく、何を変更したか
3. なぜ `out/` を直接編集しないのか
4. 新しいTeradata SQLが追加されたとき、どの処理を再実行するか

## 実案件ではどう広がるか

実案件でも基本は同じで、生成物を直接編集せず、中央の変換処理を修正して再生成する。

```text
標準変換
→ override
→ 変換後の決定的な fixup
→ BTEQなどのカスタム変換
→ 出力カバレッジ・構文・E2E結果の検証
```

ただし、最初からすべてを一つのハンズオンに入れると、何を学ぶのか分かりにくくなる。今回は最初の改善ループだけを扱う。

BTEQでは、SQLが構文エラーになるだけでなく、制御命令やファイル自体が変換対象から落ちる場合がある。そのため実案件では、SQL構文チェックだけでなく、入力と出力のカバレッジ確認や結果比較も必要になる。

大量のSQLを検証する段階では、[`databricks-sql-validator`](https://github.com/nakazax/databricks-sql-validator) の利用も検討する。
