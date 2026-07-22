#!/usr/bin/env python3
"""SQL ファイルの構文を Databricks SQL Warehouse の EXPLAIN で一括チェックする。

対象ディレクトリ配下の *.sql をステートメント単位に分割し、それぞれ
EXPLAIN <statement> を SQL Warehouse で実行して構文エラーを検出する。

使い方:
    python3 tools/check_sql.py <SQLディレクトリ> --profile <your-profile>

判定:
    OK        : EXPLAIN 成功
    OK_SYNTAX : 構文は正しいが、参照先が存在しない (TABLE_OR_VIEW_NOT_FOUND 等)。
                チェック用スキーマを用意していなくても構文検証はできるよう、既定では合格扱い
    FAIL      : 構文エラー (PARSE_SYNTAX_ERROR 等)

終了コード: FAIL が 1 件以上あれば 1、全て OK / OK_SYNTAX なら 0。

依存: Databricks CLI (`databricks`) と、プロファイルに設定済みの `warehouse_id` のみ。
"""

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ANALYSIS_ERROR_PREFIXES = (
    "TABLE_OR_VIEW_NOT_FOUND",
    "SCHEMA_NOT_FOUND",
    "CATALOG_NOT_FOUND",
    "UNRESOLVED_COLUMN",
    "UNRESOLVED_ROUTINE",
    "UNRESOLVED_FIELD",
    "NO_DEFAULT_CATALOG",
)


def split_statements(sql_text: str) -> list[str]:
    """セミコロンでステートメント分割する。

    以下の内側のセミコロンでは分割しない:
    - シングル/ダブルクォート文字列
    - `--` 行コメント、`/* */` ブロックコメント
    - BEGIN ... END / CASE ... END ブロック (プロシージャ本体や CASE 式を 1 文として保つ)

    深さ管理の詳細:
    - `BEGIN` / `CASE` で +1。ただし `BEGIN TRAN(SACTION)` は対応する END を持たないため数えない
    - `END` で -1。ただし SQL スクリプティングの `END IF` / `END WHILE` / `END FOR` /
      `END REPEAT` / `END LOOP` は対応する開始語を数えていないため減算しない
    """
    statements = []
    buffer = []
    depth = 0
    index = 0
    length = len(sql_text)
    state = "code"
    word_pattern = re.compile(r"[A-Za-z_]+")

    while index < length:
        character = sql_text[index]
        next_character = sql_text[index + 1] if index + 1 < length else ""

        if state == "squote":
            buffer.append(character)
            if character == "'":
                state = "code" if next_character != "'" else state
                if next_character == "'":
                    buffer.append(next_character)
                    index += 1
            index += 1
            continue
        if state == "dquote":
            buffer.append(character)
            if character == '"':
                state = "code"
            index += 1
            continue
        if state == "line_comment":
            buffer.append(character)
            if character == "\n":
                state = "code"
            index += 1
            continue
        if state == "block_comment":
            buffer.append(character)
            if character == "*" and next_character == "/":
                buffer.append(next_character)
                index += 2
                state = "code"
                continue
            index += 1
            continue

        if character == "'":
            state = "squote"
            buffer.append(character)
            index += 1
            continue
        if character == '"':
            state = "dquote"
            buffer.append(character)
            index += 1
            continue
        if character == "-" and next_character == "-":
            state = "line_comment"
            buffer.append(character)
            index += 1
            continue
        if character == "/" and next_character == "*":
            state = "block_comment"
            buffer.append(character)
            index += 1
            continue
        if word_pattern.match(character):
            match = word_pattern.match(sql_text, index)
            if match is None:
                raise RuntimeError("単語の解析に失敗しました")
            word = match.group(0)
            upper = word.upper()
            next_word = _peek_word(sql_text, match.end(), word_pattern)
            if upper == "CASE":
                depth += 1
            elif upper == "BEGIN" and next_word not in ("TRAN", "TRANSACTION"):
                depth += 1
            elif upper == "END" and next_word not in ("IF", "WHILE", "FOR", "REPEAT", "LOOP"):
                depth = max(0, depth - 1)
            buffer.append(word)
            index = match.end()
            continue
        if character == ";" and depth == 0:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue
        buffer.append(character)
        index += 1

    tail = "".join(buffer).strip()
    if tail and not _is_comment_only(tail):
        statements.append(tail)
    return [s for s in statements if not _is_comment_only(s)]


def _peek_word(text: str, position: int, word_pattern: re.Pattern) -> str:
    """position 以降の空白を読み飛ばし、次の単語を大文字で返す。"""
    while position < len(text) and text[position] in " \t\r\n":
        position += 1
    match = word_pattern.match(text, position)
    return match.group(0).upper() if match else ""


def _is_comment_only(stmt: str) -> bool:
    no_block = re.sub(r"/\*.*?\*/", "", stmt, flags=re.DOTALL)
    lines = [line.strip() for line in no_block.splitlines()]
    return all(not line or line.startswith("--") for line in lines)


def read_warehouse_id(profile: str) -> str:
    cfg_path = os.environ.get("DATABRICKS_CONFIG_FILE", str(Path.home() / ".databrickscfg"))
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    if profile not in cfg or "warehouse_id" not in cfg[profile]:
        sys.exit(
            f"エラー: {cfg_path} の [{profile}] に warehouse_id がありません。"
            " SETUP.md の「warehouse_id の追記」を参照してください。"
        )
    return cfg[profile]["warehouse_id"]


def _classify(message: str) -> tuple[str, str]:
    """エラーメッセージ中の error class から判定を返す。"""
    match = re.search(r"\[([A-Z0-9_.]+)\]", message)
    error_class = match.group(1) if match else ""
    if any(error_class.startswith(prefix) for prefix in ANALYSIS_ERROR_PREFIXES):
        return "OK_SYNTAX", message
    return "FAIL", message


def run_explain(statement: str, warehouse_id: str, profile: str) -> tuple[str, str]:
    """EXPLAIN を実行し (判定, エラーメッセージ) を返す。

    エラーの現れ方は 2 通りある (実測):
    - パースエラー等: statement が FAILED になり status.error.message に詳細
    - 解析エラー (存在しないテーブル参照等): statement は SUCCEEDED だが、
      EXPLAIN の結果本文が "Error occurred during query planning:" で始まり、
      続く行に [ERROR_CLASS] 付きの詳細が入る
    """
    payload = {
        "warehouse_id": warehouse_id,
        "statement": f"EXPLAIN {statement}",
        "wait_timeout": "50s",
        "on_wait_timeout": "CANCEL",
    }
    try:
        proc = subprocess.run(
            ["databricks", "api", "post", "/api/2.0/sql/statements",
             "--profile", profile, "--json", json.dumps(payload)],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        sys.exit(
            "エラー: Databricks CLI (`databricks`) が見つかりません。"
            " SETUP.md の Databricks CLI セットアップを確認してください。"
        )
    if proc.returncode != 0:
        sys.exit(f"エラー: databricks CLI の呼び出しに失敗しました:\n{proc.stderr.strip()}")
    resp = json.loads(proc.stdout)
    state = resp.get("status", {}).get("state")
    if state == "SUCCEEDED":
        rows = (resp.get("result") or {}).get("data_array") or []
        plan_text = "\n".join(row[0] or "" for row in rows if row)
        if plan_text.startswith("Error occurred during query planning"):
            return _classify(plan_text)
        return "OK", ""
    if state == "FAILED":
        message = resp.get("status", {}).get("error", {}).get("message", "(詳細不明)")
        return _classify(message)
    return "FAIL", f"statement が {state} で終了しました (タイムアウト等)"


def main() -> None:
    parser = argparse.ArgumentParser(description="EXPLAIN による SQL 構文一括チェック")
    parser.add_argument("target", help="チェック対象ディレクトリ (または単一 .sql ファイル)")
    parser.add_argument("--profile", required=True, help="Databricks CLI プロファイル名")
    parser.add_argument(
        "--strict", action="store_true",
        help="OK_SYNTAX (参照先が存在しない) も FAIL として扱う",
    )
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_file():
        sql_files = [target]
    else:
        sql_files = sorted(target.rglob("*.sql"))
    if not sql_files:
        sys.exit(f"エラー: {target} に .sql ファイルが見つかりません")

    warehouse_id = read_warehouse_id(args.profile)

    total = {"OK": 0, "OK_SYNTAX": 0, "FAIL": 0}
    failed_files = set()
    for path in sql_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        statements = split_statements(text)
        if not statements:
            print(f"  SKIP      {path} (ステートメントなし)")
            continue
        for statement_index, statement in enumerate(statements, start=1):
            verdict, message = run_explain(statement, warehouse_id, args.profile)
            if args.strict and verdict == "OK_SYNTAX":
                verdict = "FAIL"
            total[verdict] += 1
            label = f"{path} [{statement_index}/{len(statements)}]"
            if verdict == "FAIL":
                failed_files.add(str(path))
                detail = next((line for line in message.splitlines() if line.strip()), "")
                print(f"  FAIL      {label}\n            {detail[:160]}")
            elif verdict == "OK_SYNTAX":
                match = re.search(r"\[([A-Z0-9_.]+)\]", message)
                print(f"  OK_SYNTAX {label} ({match.group(1) if match else '?'})")
            else:
                print(f"  OK        {label}")

    print()
    print(f"結果: OK={total['OK']}  OK_SYNTAX={total['OK_SYNTAX']}  FAIL={total['FAIL']}")
    if failed_files:
        print("FAIL のファイル:")
        for failed_file in sorted(failed_files):
            print(f"  - {failed_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
