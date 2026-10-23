"""コールセンター 回答支援エージェント（改善版 v2）

LangGraph の create_agent ＋ ChatDatabricks（Claude）。ツールは tools.py。
06_デプロイと監視 で、このファイルを組み込んだアプリ（このフォルダ）をデプロイする。

初版（v1）からの変更点:
1. 手順・守るルール・回答の形式をシステムプロンプトに加える（製品情報の照会を必ず最初に行う、など）
2. 照会した型番で絞り込んで検索する（似た型番の説明書の取り違えを防ぐ）
"""
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks
from langchain.agents import create_agent
from langchain_core.tools import tool

from tools import CASE_STORE, CONFIG, DOC_STORE, format_docs, make_product_info_tool, make_retriever

SYSTEM_PROMPT = """あなたはブリックス電機のコールセンターで、オペレーターを支援するアシスタントです。
オペレーターからの相談の文章から、製造番号・購入日・症状を読み取り、お客様への回答案を作成してください。

## 手順（必ずこの順で行う）
1. 最初に get_product_info で製造番号を照会し、型番・ロット・製造月・保証の状態を確認する。照会できない場合は推測せず「担当者に確認」とする。
2. search_documents に、照会した型番（model_no）を必ず指定して、取扱説明書とサービス技術情報を検索する。
3. 無償点検の対象かを確認するため、「<型番> 無償点検」でもサービス技術情報を検索し、対象ロット・製造月と照会結果を照らし合わせる。
4. 必要に応じて search_past_cases に型番を指定して、似た症状の過去の対応を参考にする。

## 守るルール
- 分解する、カバーや裏ぶたを開ける、内部を確認するなどの作業を案内しない。
- 煙・焦げ臭さ・火花・異常な発熱・水漏れなど安全に関わる症状がある場合は、すぐに使用を中止し、電源プラグを抜くよう最初に案内する。
- 故障や不良品と断定しない。保証規定にない補償（返金・クーポンなど）を提案しない。
- 回答は、検索した文書に書かれている内容に基づける。書かれていないことは推測しない。
- 回答に個人情報（氏名・電話番号・住所など）を含めない。

## 回答の形式
（調べた結果）型番・ロット・保証の状態・無償点検の対象かどうか
お客様への回答案（丁寧な話し言葉、手順は番号付き）
次の対応: 一次対処で様子を見る／使用を中止して修理受付／無償点検を手配／使用を中止して至急対応／担当者に確認 のどれか1つ
根拠: 参照した文書名"""


def build_tools(w: WorkspaceClient) -> list:
    retrieve = make_retriever(w)

    @tool
    def search_documents(query: str, model_no: str) -> str:
        """取扱説明書・サービス技術情報・保証規定を検索します。model_no には get_product_info で確認した型番（例: RC-550）を必ず指定します。"""
        return format_docs(retrieve(DOC_STORE, query, filters={"model_no": [model_no, "ALL"]}))

    @tool
    def search_past_cases(query: str, model_no: str) -> str:
        """過去の修理受付の対応事例（個人情報はマスク済み）を、型番で絞り込んで検索します。"""
        return format_docs(retrieve(CASE_STORE, query, filters={"model_no": model_no}))

    return [make_product_info_tool(w), search_documents, search_past_cases]


def build_agent(w: WorkspaceClient | None = None, checkpointer=None):
    """エージェントを組み立てる。w を省略すると、実行環境の既定の認証を使う。"""
    w = w or WorkspaceClient()
    return create_agent(model=ChatDatabricks(endpoint=CONFIG["llm_endpoint"]), tools=build_tools(w),
                        system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)
