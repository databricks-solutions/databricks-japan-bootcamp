"""エージェントのツールと、v1・v2 で共通の部品。

- 名前（モデル・インデックス・関数）は、同じフォルダの config.yaml から読む（00_設定 が書き出す）
- 認証は WorkspaceClient で受け取る。ノートブックでは実行している人、アプリではアプリのサービスプリンシパルになる
"""
import asyncio
import contextvars
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mlflow
import yaml
from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient
from langchain_core.documents import Document
from langchain_core.tools import tool
from mlflow.entities import SpanType

# LangGraph のトレースを有効にする（サーバーレスのノートブックでは自動で有効にならないので、明示的に呼ぶ）
mlflow.langchain.autolog()

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())

# 検索するインデックスと、取り出す列（text は回答の根拠としてエージェントに渡す本文）
DOC_STORE = dict(index=CONFIG["doc_index"], columns=["chunk_id", "source_file", "doc_type", "model_no"], text="chunk_to_embed")
CASE_STORE = dict(index=CONFIG["case_index"], columns=["request_id", "model_no", "symptom_category", "result_category"], text="case_text")


def make_retriever(w: WorkspaceClient):
    """AI Search の検索。トレースでは RETRIEVER として記録する（検索の評価に使う）。"""

    @mlflow.trace(span_type=SpanType.RETRIEVER)
    def retrieve(store: dict, query: str, filters: dict | None = None, k: int = 5) -> list[Document]:
        # 検索文をそのまま渡す（埋め込みの計算は AI Search 側で行う）
        for attempt in range(10):   # インデックスを作り直した直後は「not ready」になることがあるので、少し待って呼び直す
            try:
                res = w.vector_search_indexes.query_index(store["index"], columns=store["columns"] + [store["text"]], query_text=query,
                                                          num_results=k, filters_json=json.dumps(filters) if filters else None)
                break
            except Exception as e:
                if "not ready" not in str(e) or attempt == 9:
                    raise
                time.sleep(10)
        names = [c.name for c in res.manifest.columns]
        rows = [dict(zip(names, r)) for r in (res.result.data_array or [])]
        return [Document(page_content=r[store["text"]], metadata={c: r[c] for c in store["columns"]}) for r in rows]

    return retrieve


def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(f"[{d.metadata.get('source_file') or d.metadata.get('request_id')}] (型番: {d.metadata.get('model_no')})\n{d.page_content}"
                       for d in docs)


def make_product_info_tool(w: WorkspaceClient):
    """製品情報の照会（UC関数）。Databricks が管理する MCP サーバー経由で呼ぶ。"""
    catalog, schema, function = CONFIG["product_function"].split(".")
    mcp = DatabricksMCPClient(server_url=f"{w.config.host}/api/2.0/mcp/functions/{catalog}/{schema}", workspace_client=w)
    mcp_name = f"{catalog}__{schema}__{function}"   # MCP サーバーでのツールの名前

    @tool
    def get_product_info(serial_no: str, purchase_date: str) -> str:
        """製造番号から、型番・製品名・ロット番号・製造月・製造工場・保証の状態を調べます。purchase_date は購入日（YYYY-MM-DD）。わからない場合は空文字。"""
        for attempt in range(5):   # 呼び出しが集中して断られた（429）ときは、少し待ってから呼び直す
            try:
                res = _run_async(mcp.acall_tool(mcp_name, {"serial_no": serial_no, "purchase_date": purchase_date}))
                return "".join(getattr(c, "text", "") for c in res.content)
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)

    return get_product_info


def _run_async(coro):
    """非同期の処理を別のスレッドで実行する（ノートブックなど、すでにイベントループが動いている所からも呼べるように）。"""
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(contextvars.copy_context().run, asyncio.run, coro).result()


def to_text(content) -> str:
    """Claude の推論ブロックを除き、回答のテキストだけを取り出す（画面や評価に出すとき用。エージェントの中では推論も残す）。

    content は「部品のリスト」か、「部品のリストの JSON（いくつか続くことがある）＋本文」の文字列。
    """
    parts, rest = [], content
    if isinstance(content, str):
        decoder, rest = json.JSONDecoder(), content.lstrip()
        while rest.startswith("[{"):
            try:
                value, end = decoder.raw_decode(rest)
            except json.JSONDecodeError:
                break
            parts += value if isinstance(value, list) else [value]
            rest = rest[end:].lstrip()
    else:
        parts, rest = list(content or []), ""
    return "".join(c.get("text", "") for c in parts if isinstance(c, dict) and c.get("type") == "text") + rest
