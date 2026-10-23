"""DurableAgentServer（AgentKit）から呼ばれるエージェントの入り口。

`agentbricks init --framework langgraph` のテンプレートの agent/agent.py をもとにしている。
エージェントの本体は agent_v2.py（ノートブックで評価した改善版と同じファイル）。
"""
from collections.abc import AsyncGenerator, Callable
from typing import Any

from databricks.sdk import WorkspaceClient

import agent_v2
from tools import CONFIG
from databricks_agentkit import workspace_client
from databricks_agentkit.langgraph import checkpointer, configure_tracing, start_trace, thread_config
from databricks_agentkit.langgraph.session_store import invocation_id_from_metadata, invocation_metadata

# チャット画面のモデルの表示に使う（エージェントは常に config.yaml のモデルを使う）
MODEL = CONFIG["llm_endpoint"]


def configure() -> None:
    """サーバーの起動時に1回呼ばれる。"""
    workspace_client()   # 認証の設定を確かめる（アプリではサービスプリンシパル）
    configure_tracing()  # MLFLOW_TRACKING_URI・MLFLOW_EXPERIMENT_ID の実験にトレースを送る


async def create_agent_graph(actor: str, model: str | None = None, *,
                             workspace_client_for: Callable[[str], WorkspaceClient] | None = None):
    return agent_v2.build_agent(checkpointer=checkpointer())   # アプリのサービスプリンシパルの権限で動く


async def recovery_input(agent_input: Any, *, session_id: str, actor: str, invocation_id: str) -> Any:
    """途中で止まった実行を再開するときの入力（テンプレートのまま）。"""
    checkpoint = await checkpointer().aget_tuple(thread_config(session_id, actor))
    checkpointed = bool(checkpoint and invocation_id_from_metadata(checkpoint.metadata) == invocation_id)
    return None if checkpointed else agent_input


async def run_agent(agent_input: Any, *, session_id: str, actor: str | None = None, model: str | None = None,
                    invocation_id: str | None = None,
                    workspace_client_for: Callable[[str], WorkspaceClient] | None = None,
                    graph: Any = None) -> AsyncGenerator[Any, None]:
    """エージェントを実行し、LangGraph のイベントを返す（テンプレートのまま）。"""
    actor = actor or session_id
    if graph is None:
        graph = await create_agent_graph(actor, model, workspace_client_for=workspace_client_for)
    config = thread_config(session_id, actor)
    if invocation_id:
        config["metadata"] = invocation_metadata(invocation_id)
    last_update: Any = None
    with start_trace(name="invoke", inputs=agent_input, session_id=session_id) as span:
        async for event in graph.astream(input=agent_input, config=config, stream_mode=["updates", "messages"], durability="sync"):
            if event[0] == "updates":
                last_update = event[1]
            yield event
        if span is not None and last_update is not None:
            span.set_outputs(last_update)
