"""HTTP 200のポリシー拒否を、通常応答・APIエラーと区別する。"""

import ast
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import textwrap
import unittest
from unittest.mock import Mock


NOTEBOOK = Path(__file__).resolve().parents[1] / "LLMOps_ハンズオン_generic.py"


class Response:
    def __init__(self, policy=None, tool_calls=None):
        self.policy = policy
        self.choices = [SimpleNamespace(message=SimpleNamespace(
            content="回答", tool_calls=tool_calls,
        ))]
        self.usage = SimpleNamespace(prompt_tokens=12, completion_tokens=8)

    def model_dump(self, **kwargs):
        return {} if self.policy is None else {"databricks_service_policy": self.policy}


@contextlib.contextmanager
def span(**kwargs):
    yield SimpleNamespace(set_inputs=lambda value: None, set_outputs=lambda value: None)


class WorkshopTest(unittest.TestCase):
    def setUp(self):
        self.create = Mock()
        self.search = Mock(return_value="商品情報")
        self.env = {
            "json": json,
            "textwrap": textwrap,
            "client": SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))),
            "mlflow": SimpleNamespace(start_span=span, genai=SimpleNamespace(load_prompt=Mock(
                return_value=SimpleNamespace(format=lambda **kwargs: "ルール", version=1),
            ))),
            "SERVICE_NAME": "workshop.llmops.ws_test",
            "SYSTEM_PROMPT": "ルール",
            "PROMPT_NAME": "workshop.llmops.prompt_test",
            "COMPANY_NAME": "サンプル株式会社",
            "search_products": self.search,
            "tools": [],
        }
        names = {"WorkshopPolicyBlocked", "call_gateway", "query_llm", "run_agent", "run_agent_with_registry"}
        definitions = []
        for node in ast.parse(NOTEBOOK.read_text()).body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
                if isinstance(node, ast.FunctionDef):
                    node.decorator_list = []
                definitions.append(node)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(NOTEBOOK), "exec"), self.env)
        self.console = io.StringIO()
        redirect = contextlib.redirect_stdout(self.console)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_allowed_response_uses_chat_completions(self):
        response = Response()
        self.create.return_value = response
        self.assertIs(self.env["query_llm"]("質問"), response)
        self.assertEqual(self.create.call_args.kwargs["model"], "workshop.llmops.ws_test")
        self.assertEqual(self.create.call_args.kwargs["messages"], [{"role": "user", "content": "質問"}])
        self.assertIn("[通過]", self.console.getvalue())

    def test_http_200_denial_is_not_displayed_as_allowed(self):
        self.create.return_value = Response(policy={"reason": "blocked by policy"})
        self.assertIsNone(self.env["query_llm"]("質問"))
        self.assertIn("[ブロック]", self.console.getvalue())
        self.assertNotIn("[通過]", self.console.getvalue())

    def test_api_failure_is_not_a_successful_guardrail_test(self):
        self.create.side_effect = RuntimeError("guardrail evaluator unavailable")
        with self.assertRaisesRegex(RuntimeError, "evaluator unavailable"):
            self.env["query_llm"]("質問")
        self.assertIn("[エラー]", self.console.getvalue())
        self.assertNotIn("[ブロック]", self.console.getvalue())

    def test_input_denial_stops_before_tools(self):
        self.create.return_value = Response(policy={"reason": "denied"})
        with self.assertRaises(self.env["WorkshopPolicyBlocked"]):
            self.env["run_agent"]("質問")
        self.search.assert_not_called()
        self.assertEqual(self.create.call_count, 1)

    def test_final_denial_is_not_displayed_as_an_agent_answer(self):
        call = SimpleNamespace(id="call_1", function=SimpleNamespace(arguments='{"keyword":"ライト"}'))
        self.create.side_effect = [Response(tool_calls=[call]), Response(policy={"reason": "output denied"})]
        with self.assertRaises(self.env["WorkshopPolicyBlocked"]):
            self.env["run_agent"]("質問")
        self.search.assert_called_once_with(keyword="ライト")
        self.assertNotIn("[エージェント回答]", self.console.getvalue())

    def test_registry_agent_also_stops_on_denial(self):
        self.create.return_value = Response(policy={"reason": "denied"})
        with self.assertRaises(self.env["WorkshopPolicyBlocked"]):
            self.env["run_agent_with_registry"]("質問")
        self.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
