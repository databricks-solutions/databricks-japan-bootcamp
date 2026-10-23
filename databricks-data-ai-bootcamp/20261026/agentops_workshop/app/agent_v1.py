"""コールセンター 回答支援エージェント（初版 v1）

LangGraph の create_agent ＋ ChatDatabricks（Claude）。ツールは tools.py。
"""
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks
from langchain.agents import create_agent
from langchain_core.tools import tool

from tools import CASE_STORE, CONFIG, DOC_STORE, format_docs, make_product_info_tool, make_retriever

SYSTEM_PROMPT = """あなたはブリックス電機のコールセンターで、オペレーターを支援するアシスタントです。
オペレーターからの相談の文章から、製造番号・購入日・症状を読み取り、お客様への回答案を作成してください。"""


def build_tools(w: WorkspaceClient) -> list:
    retrieve = make_retriever(w)

    @tool
    def search_documents(query: str) -> str:
        """取扱説明書・サービス技術情報・保証規定を検索します。"""
        return format_docs(retrieve(DOC_STORE, query))

    @tool
    def search_past_cases(query: str) -> str:
        """過去の修理受付の対応事例（個人情報はマスク済み）を検索します。"""
        return format_docs(retrieve(CASE_STORE, query))

    return [make_product_info_tool(w), search_documents, search_past_cases]


def build_agent(w: WorkspaceClient | None = None, checkpointer=None):
    """エージェントを組み立てる。w を省略すると、実行環境の既定の認証を使う。"""
    w = w or WorkspaceClient()
    return create_agent(model=ChatDatabricks(endpoint=CONFIG["llm_endpoint"]), tools=build_tools(w),
                        system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)
