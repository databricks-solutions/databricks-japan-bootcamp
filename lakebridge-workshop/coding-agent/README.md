# コーディングエージェント併用ハンズオン (Teradata)

BladeBridge の標準変換で残った Teradata 構文を override で補正し、同じ入力から変換し直す手順を扱う。変換済みの SQL を手で直すのではなく、再利用できる変換ルールに修正を残す。

override の設定項目と記述方法は公式ドキュメントの [BladeBridge Configuration](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/bladebridge/bladebridge_configuration/) を参照。

> **前提**
> - 共通セットアップ ([SETUP.md](../SETUP.md)) が完了していること
> - `warehouse_id` に Serverless SQL Warehouse を設定していること。クラシック Warehouse は停止状態からの起動に時間がかかり、構文チェックがタイムアウトして FAIL 扱いになる場合がある
> - Claude Code / Codex などのコーディングエージェントを利用できること

## 60分の進め方

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

この60分では、標準変換、override の追加、再変換、構文確認まで進める。BTEQ、ストアドプロシージャの再設計、結果データの一致検証は扱わない。

## 使用するファイル

| パス | 用途 |
|---|---|
| `input/01_identity.sql` | `NO CYCLE` を含む Teradata の IDENTITY 列 |
| `input/02_update_from.sql` | Teradata の `UPDATE ... FROM` |
| `overrides/teradata-overrides.json` | 演習で編集する BladeBridge override テンプレート |
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

期待結果は `FAIL=2`。バージョンにより変換結果や件数が変わる場合は、件数ではなく実際の出力を確認する。

この時点の例は [`_reference_output/before/`](_reference_output/before/) にある。

## 3. エージェントに変換ルールを作らせる

ここでは `out/before/` の SQL を手で直さず、再利用できる override の作成をエージェントに依頼する。

override の設定項目と記述方法は BladeBridge 固有のため、作業時は公式の [BladeBridge Configuration](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/bladebridge/bladebridge_configuration/) を参照する。この演習では `line_subst` と `block_subst` を使用する。

まず `coding-agent/` ディレクトリでコーディングエージェントを起動する。

```bash
# lakebridge-workshop/coding-agent/ で実行する (どちらか利用できるもの)
claude
codex
```

起動したら次のプロンプトを渡す。渡す前に、`<your-profile>` を自分の Databricks CLI プロファイル名へ置き換える。

```text
input/ は Teradata SQL、out/before/ は BladeBridge の標準変換結果です。

python3 tools/check_sql.py out/before --profile <your-profile>

の失敗を分析し、同じ input/ から構文チェックを通る SQL を再生成できるように、
overrides/teradata-overrides.json に BladeBridge override を実装してください。

- override の仕様は次の公式ドキュメントを読んでから実装すること:
  https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/bladebridge/bladebridge_configuration/
- out/before/ の SQL を直接編集しないこと
- input/ の意味を変えないこと
- inherit_from の __BLADEBRIDGE_BASE_CONFIG__ は変更しないこと
- 適用範囲が広すぎる正規表現を避けること
- 再変換と検証は README.md の「4. override付きで再変換する」を参照すること
- 変更後の再変換コマンドと検証コマンドを示すこと
```

BladeBridge の override 記法は一般的な知識ではないため、エージェント任せにせずドキュメントを読ませるのが確実に進めるポイント。エージェントがインターネットへアクセスできない環境では、上記ページをブラウザで PDF またはテキストとして保存して `coding-agent/` 配下に置き、プロンプトの参照先を URL からそのファイルパスに差し替える。

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

期待結果は `FAIL=0`。

- `NO CYCLE` が削除される
- `UPDATE ... FROM` が `MERGE INTO` に変換される
- `out/before/` は手で修正していない
- 同じ入力とoverrideから、結果を再生成できる

完成したSQLの例は [`_reference_output/solution/`](_reference_output/solution/) にある。

## 5. 作業後の確認

作業が終わったら、以下を確認する。

1. 標準変換後の `out/before/` には、`NO CYCLE` と Teradata 形式の `UPDATE ... FROM` が残っている
2. 生成された SQL ではなく、`overrides/teradata-overrides.json` を修正している
3. 同じ入力と override から `out/solution/` を再生成できる
4. 入力 SQL を追加した場合も、変換、構文確認、override の修正、再変換の順に進められる

## 演習範囲外の処理

実際の移行では、override だけで処理できないパターンに対応するため、後処理や専用変換、追加の検証を組み合わせる。

```text
標準変換
→ override
→ 変換後の決定的な fixup
→ BTEQなどのカスタム変換
→ 出力カバレッジ・構文・E2E結果の検証
```

この演習で実施するのは、標準変換から override 適用後の構文確認まで。fixup、BTEQ の変換、出力カバレッジや結果データの検証は対象外とする。

BTEQ では、制御命令が変換されずに残る場合や、BladeBridge がファイルを出力しない場合がある。そのため、SQL の構文チェックに加えて、入力と出力の件数確認や結果比較も必要になる。

大量のSQLを検証する段階では、[`databricks-sql-validator`](https://github.com/nakazax/databricks-sql-validator) の利用も検討する。
