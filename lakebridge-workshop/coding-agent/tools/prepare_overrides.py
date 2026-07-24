#!/usr/bin/env python3
"""BladeBridge override テンプレートをローカル実行用に展開する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_CONFIG_TOKEN = "__BLADEBRIDGE_BASE_CONFIG__"
BASE_CONFIG_GLOB = (
    ".databricks/labs/remorph-transpilers/bladebridge/lib/.venv/lib/"
    "python*/site-packages/databricks/labs/bladebridge/Converter/Configs/"
    "Teradata/base_teradata2databricks_sql.json"
)


def find_base_config() -> Path:
    candidates = list(Path.home().glob(BASE_CONFIG_GLOB))
    if not candidates:
        raise SystemExit(
            "エラー: BladeBridge の Teradata ベース設定が見つかりません。"
            " SETUP.md の Converter プラグインのインストールを確認してください。"
        )
    return max(candidates, key=lambda candidate: candidate.stat().st_mtime).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="override テンプレートのベース設定トークンをローカル絶対パスへ置換"
    )
    parser.add_argument("source", type=Path, help="override テンプレート")
    parser.add_argument("destination", type=Path, help="生成する実行用 override")
    args = parser.parse_args()

    source_text = args.source.read_text(encoding="utf-8")
    json.loads(source_text)
    if BASE_CONFIG_TOKEN not in source_text:
        raise SystemExit(
            f"エラー: {args.source} に {BASE_CONFIG_TOKEN} がありません。"
        )

    output_text = source_text.replace(BASE_CONFIG_TOKEN, str(find_base_config()))
    json.loads(output_text)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(output_text, encoding="utf-8")
    print(f"生成: {args.destination}")


if __name__ == "__main__":
    main()
