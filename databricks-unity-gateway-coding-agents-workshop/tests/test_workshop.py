"""Workspace設定の保持と、Notebook全セル実行時の書き込み防止を検証する。"""

import ast
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "Unity_Gateway_ハンズオン.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
# Databricks外では、関数と定数だけを読み込んでAPIをモックする。
DEFINITIONS = ast.Module(
    body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)
          or (isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id in
                      {"CONFIG_API", "SERVER_FIELDS", "CLAUDE_AGENT"} for t in node.targets))],
    type_ignores=[],
)
NAMESPACE = {"copy": copy, "hashlib": hashlib, "json": __import__("json"), "re": re,
             "shlex": shlex, "datetime": datetime, "timezone": timezone}
exec(compile(DEFINITIONS, str(ROOT), "exec"), NAMESPACE)


def baseline_config():
    return {
        "name": "coding-agent-configs/workshop", "update_time": "2026-11-02T00:00:00Z",
        "spec_version": 1, "retrieved_time": "2026-11-02T00:01:00Z",
        "default_agent": "CODING_AGENT_CODEX",
        "enabled_agents": [
            {"agent": "CODING_AGENT_CODEX", "config": {"models": {"model_services": ["system.ai.gpt-5-6-sol"]}}},
            {"agent": NAMESPACE["CLAUDE_AGENT"], "config": {
                "models": {"unity_catalog_location": "system.ai"},
                "default_models": {"default_fable_model": "system.ai.previous-model"},
                "http_headers": {"x-team": "workshop"},
                "agent_native_settings": {"deniedMcpServers": [{"serverName": "blocked"}]},
            }},
        ],
        "mcp_servers": {"names": ["main.tools.demo"]},
        "skills": {"names": ["main.skills.review"]},
    }


class ConfigTests(unittest.TestCase):
    models = ["system.ai.claude-sonnet-5", "system.ai.claude-haiku-4-5"]

    def test_service_selection_preserves_existing_name_and_rejects_incomplete_names(self):
        choose = NAMESPACE["workshop_service_name"]
        self.assertEqual(choose("training-catalog", "hands_on", "first.last-test@example.com"),
                         "training-catalog.hands_on.coding_agent_first_last_test")
        existing = "llmops-ai-governance-workshop.custom.guardrail_demo_first_last_test"
        # 前編のソースファイルを参照せず、任意の既存サービス名を保持する。
        self.assertEqual(choose("new-catalog", "new_schema", "another@example.com", existing), existing)
        for invalid in ("service", "catalog.schema", "catalog..service", "model-services/catalog.schema.service"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                choose("training-catalog", "hands_on", "user@example.com", invalid)

    def test_generated_service_names_handle_aliases_case_and_long_names(self):
        choose = NAMESPACE["workshop_service_name"]
        self.assertEqual(choose("c", "s", "First.Last-TEST@example.com"),
                         "c.s.coding_agent_first_last_test")
        alias = choose("c", "s", "alice+work@example.com")
        self.assertRegex(alias.split(".")[-1], r"^coding_agent_[a-z0-9_]+$")
        self.assertNotEqual(alias, choose("c", "s", "alice_work@example.com"))
        self.assertLessEqual(len(choose("c", "s", "a" * 300 + "@example.com").split(".")[-1]), 255)

    def test_merge_preserves_other_agents_and_settings_without_mutating_input(self):
        baseline = baseline_config()
        snapshot = copy.deepcopy(baseline)
        proposed = NAMESPACE["configure_claude"](baseline, self.models, smart_routing=True)
        self.assertEqual(baseline, snapshot)
        for key in ("mcp_servers", "skills"):
            self.assertEqual(proposed[key], baseline[key])
        self.assertEqual(proposed["enabled_agents"][0], baseline["enabled_agents"][0])
        self.assertEqual(proposed["default_agent"], baseline["default_agent"])
        claude = proposed["enabled_agents"][1]["config"]
        self.assertEqual(claude["http_headers"], {"x-team": "workshop"})
        self.assertEqual(claude["agent_native_settings"], baseline["enabled_agents"][1]["config"]["agent_native_settings"])
        self.assertEqual(set(claude["models"]), {"model_services"})
        self.assertTrue(set(claude["default_models"].values()) <= set(self.models))
        self.assertTrue(set(proposed).isdisjoint(NAMESPACE["SERVER_FIELDS"]))
        self.assertEqual(proposed, NAMESPACE["configure_claude"](proposed, self.models, smart_routing=True))

    def test_new_config_initializes_default_agent_but_existing_default_is_preserved(self):
        create = NAMESPACE["configure_claude"](None, self.models, smart_routing=True)
        self.assertEqual(create["default_agent"], NAMESPACE["CLAUDE_AGENT"])
        for default_agent in ("CODING_AGENT_CODEX", "CODING_AGENT_GITHUB_COPILOT"):
            baseline = dict(baseline_config(), default_agent=default_agent)
            self.assertEqual(NAMESPACE["configure_claude"](baseline, self.models, smart_routing=True)["default_agent"],
                             default_agent)

    def test_smart_defaults_reports_missing_agent_or_dynamic_models_clearly(self):
        models = NAMESPACE["configured_claude_models"]
        with self.assertRaisesRegex(ValueError, "Claude Codeを有効"):
            models({"enabled_agents": []})
        with self.assertRaisesRegex(ValueError, "model_services"):
            models(baseline_config())

    def test_routing_rejects_custom_service_and_invalid_smart_defaults(self):
        with self.assertRaises(ValueError):
            NAMESPACE["configure_claude"](None, ["training.hands_on.demo"], smart_routing=True)
        baseline = baseline_config()
        baseline["smart_defaults"] = {"tiers": [{
            "recommended_agent": NAMESPACE["CLAUDE_AGENT"], "recommended_model": "system.ai.removed",
        }]}
        with self.assertRaises(ValueError):
            NAMESPACE["configure_claude"](baseline, self.models, smart_routing=True)

    def test_preview_does_not_call_any_api(self):
        client = Mock()
        with contextlib.redirect_stdout(io.StringIO()):
            NAMESPACE["publish_agent_config"](client, None, {"enabled_agents": []}, ["enabled_agents"])
        client.api_client.do.assert_not_called()

    def test_patch_changes_only_selected_fields(self):
        baseline = baseline_config()
        client = Mock()
        client.api_client.do.return_value = {"coding_agent_configs": [baseline]}
        proposed = NAMESPACE["configure_claude"](baseline, self.models, smart_routing=True)
        with contextlib.redirect_stdout(io.StringIO()):
            NAMESPACE["publish_agent_config"](client, baseline, proposed, ["enabled_agents"], apply=True)
        args, kwargs = client.api_client.do.call_args
        self.assertEqual(args, ("PATCH", "/api/ai-gateway/v2/coding-agent-configs/workshop"))
        self.assertEqual(kwargs["query"], {"update_mask": "enabled_agents"})
        self.assertEqual(set(kwargs["body"]), {"enabled_agents"})
        self.assertEqual(kwargs["body"]["enabled_agents"][0], baseline["enabled_agents"][0])

    def test_create_and_subsequent_update_do_not_duplicate_config(self):
        client = Mock()
        client.api_client.do.return_value = {"coding_agent_configs": []}
        proposed = NAMESPACE["configure_claude"](None, self.models, smart_routing=True)
        with contextlib.redirect_stdout(io.StringIO()):
            NAMESPACE["publish_agent_config"](client, None, proposed, ["enabled_agents"], apply=True)
        self.assertEqual(client.api_client.do.call_args.args, ("POST", NAMESPACE["CONFIG_API"]))
        saved = dict(proposed, name="coding-agent-configs/new", update_time="new")
        client.reset_mock()
        client.api_client.do.return_value = {"coding_agent_configs": [saved]}
        with contextlib.redirect_stdout(io.StringIO()):
            NAMESPACE["publish_agent_config"](client, saved, proposed, ["enabled_agents"], apply=True)
        self.assertEqual(client.api_client.do.call_args.args[0], "PATCH")

    def test_stale_baseline_stops_before_write(self):
        baseline = baseline_config()
        latest = dict(baseline, update_time="2026-11-02T01:00:00Z")
        client = Mock()
        client.api_client.do.return_value = {"coding_agent_configs": [latest]}
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            NAMESPACE["publish_agent_config"](client, baseline, baseline, ["enabled_agents"], apply=True)
        self.assertEqual(client.api_client.do.call_count, 1)

    def test_changed_content_without_changed_timestamp_stops_before_write(self):
        baseline = baseline_config()
        latest = copy.deepcopy(baseline)
        latest["default_agent"] = NAMESPACE["CLAUDE_AGENT"]
        client = Mock()
        client.api_client.do.return_value = {"coding_agent_configs": [latest]}
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            NAMESPACE["publish_agent_config"](client, baseline, baseline, ["enabled_agents"], apply=True)
        self.assertEqual(client.api_client.do.call_count, 1)

    def test_multiple_configs_and_auth_errors_are_not_suppressed(self):
        client = Mock()
        client.api_client.do.return_value = {"coding_agent_configs": [{}, {}]}
        with self.assertRaises(RuntimeError):
            NAMESPACE["read_agent_config"](client)
        client.api_client.do.side_effect = PermissionError("not authorized")
        with self.assertRaises(PermissionError):
            NAMESPACE["read_agent_config"](client)


class AnalysisTests(unittest.TestCase):
    def test_timezones_are_normalized_and_ambiguous_or_reversed_windows_are_rejected(self):
        build = NAMESPACE["build_trace_analysis"]
        args = ("2026-11-10T12:00:00+09:00", "2026-11-10T04:00:00Z",
                "training.services.mine", ["system.ai.claude-haiku-4-5"], "https://example.cloud.databricks.com")
        prompts = build(*args)
        for text in list(prompts.values())[1:]:
            self.assertIn("2026-11-10T03:00:00+00:00", text)
            self.assertIn("2026-11-10T04:00:00+00:00", text)
        for start in ("2026-11-10T03:00:00", "2026-11-10T04:00:00Z", "2026-11-10T05:00:00Z"):
            with self.subTest(start=start), self.assertRaises(ValueError):
                build(start, *args[1:])


class TerminalTests(unittest.TestCase):
    def test_browser_commands_use_session_auth_without_embedding_its_value(self):
        with patch.dict(os.environ, {"DATABRICKS_TOKEN": "offline-test-value-never-render"}):
            commands = NAMESPACE["build_terminal_commands"]("https://example.cloud.databricks.com", "browser")
        self.assertIn('DATABRICKS_BEARER="$DATABRICKS_TOKEN"', commands)
        self.assertIn("UG_SKIP_OS_SETTINGS=1", commands)
        self.assertNotIn("offline-test-value-never-render", commands)
        self.assertNotIn("--user", commands)
        self.assertNotIn("auth login", commands)

    def test_browser_without_session_credentials_stops_before_launch(self):
        commands = NAMESPACE["build_terminal_commands"]("https://example.cloud.databricks.com", "browser")
        # Tokenなしの実行ではugやmkdirへ進まない。シェルだけで検証し、外部接続しない。
        result = subprocess.run(["bash", "-c", commands], env={"PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, check=True)
        self.assertIn("認証情報が見つかりません", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_local_commands_keep_normal_oauth_and_quote_the_workspace(self):
        build = NAMESPACE["build_terminal_commands"]
        commands = build("https://example.cloud.databricks.com/?w=123&account_id=456", "local")
        self.assertIn("--workspace 'https://example.cloud.databricks.com/?w=123&account_id=456'", commands)
        self.assertNotIn("DATABRICKS_BEARER", commands)
        self.assertIn("UG_SKIP_OS_SETTINGS=1", commands)
        for terminal in ("browser", "local"):
            subprocess.run(["bash", "-n"], input=build("https://example.cloud.databricks.com", terminal),
                           capture_output=True, text=True, check=True)
        with self.assertRaises(ValueError):
            build("https://example.cloud.databricks.com", "unknown")

    def test_local_configuration_failure_stops_before_agent_launch(self):
        commands = NAMESPACE["build_terminal_commands"]("https://example.cloud.databricks.com", "local")
        stub = 'ug() { if [ "$1" = configure ]; then return 23; fi; echo UNEXPECTED_AGENT_LAUNCH; };\n'
        result = subprocess.run(["bash", "-c", stub + commands], env={"PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 23)
        self.assertNotIn("UNEXPECTED_AGENT_LAUNCH", result.stdout)


class NotebookTests(unittest.TestCase):
    def run_notebook(self, api_types, widget_values=None, *, service_exists=True):
        class NotFound(Exception):
            pass
        client = Mock()
        client.current_user.me.return_value.user_name = "first.last@example.com"
        client.config.host = "https://example.cloud.databricks.com"

        def request(method, path, **kwargs):
            self.assertEqual(method, "GET", "全セル実行で書き込み要求が発生した")
            if path == NAMESPACE["CONFIG_API"]:
                return {"coding_agent_configs": [baseline_config()]}
            # Get Model Serviceの公式API契約。実機でもこのパスで取得できることを確認。
            # ドキュメントの分類名と実際のHTTPパスは異なる。
            # https://docs.databricks.com/api/ai-gateway/v1/get-model-service.md
            # GET /api/2.1/unity-catalog/{name=model-services/*}
            expected_service = (widget_values or {}).get("existing_service", "").strip() or "unity-gateway-workshop.hands_on.coding_agent_first_last"
            self.assertEqual(path, f"/api/2.1/unity-catalog/model-services/{expected_service}")
            if not service_exists:
                raise NotFound("model service not found")
            if isinstance(api_types, Exception):
                raise api_types
            return {"supported_api_types": api_types, "config": {"routing": {}}}

        client.api_client.do.side_effect = request
        sdk = types.ModuleType("databricks.sdk")
        sdk.WorkspaceClient = lambda: client
        errors = types.ModuleType("databricks.sdk.errors")
        errors.NotFound = NotFound
        modules = {"databricks": types.ModuleType("databricks"), "databricks.sdk": sdk,
                   "databricks.sdk.errors": errors}
        widgets = dict(widget_values or {})
        dbutils = Mock()
        dbutils.widgets.text.side_effect = lambda name, default, label: widgets.setdefault(name, default)
        dbutils.widgets.dropdown.side_effect = lambda name, default, options, label: widgets.setdefault(name, default)
        dbutils.widgets.get.side_effect = widgets.__getitem__
        values = {"dbutils": dbutils}
        with patch.dict(sys.modules, modules), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(SOURCE, str(ROOT), "exec"), values)
        return values

    def test_run_all_with_llama_skips_claude_registration(self):
        values = self.run_notebook(["mlflow/v1/chat/completions"])
        self.assertEqual(values["TERMINAL"], "browser")
        self.assertFalse(values["can_use_in_claude"])
        self.assertIsNone(values["phase2_config"])
        self.assertIsNone(values["smart_defaults_config"])

    def test_local_route_also_keeps_run_all_read_only(self):
        values = self.run_notebook(["mlflow/v1/chat/completions"], {"terminal": "local"})
        self.assertEqual(values["TERMINAL"], "local")

    def test_run_all_with_messages_preserves_existing_model_list(self):
        baseline = baseline_config()
        baseline["enabled_agents"][1]["config"]["models"] = {"model_services": ["system.ai.custom-choice"]}
        with patch(__name__ + ".baseline_config", return_value=baseline):
            values = self.run_notebook(["anthropic/v1/messages"])
        models = values["phase2_config"]["enabled_agents"][1]["config"]["models"]["model_services"]
        self.assertEqual(models, ["system.ai.custom-choice", values["WORKSHOP_SERVICE"]])
        self.assertEqual(values["phase1_config"]["default_agent"], baseline["default_agent"])
        self.assertEqual(values["phase2_config"]["default_agent"], baseline["default_agent"])

    def test_smart_defaults_with_budget_uses_fraction_and_preserves_default_agent(self):
        baseline = baseline_config()
        baseline["enabled_agents"][1]["config"]["models"] = {
            "model_services": ["system.ai.claude-haiku-4-5"],
        }
        with patch(__name__ + ".baseline_config", return_value=baseline):
            values = self.run_notebook(["mlflow/v1/chat/completions"], {"budget_id": "test-budget"})
        config = values["smart_defaults_config"]
        self.assertEqual(config["smart_defaults"]["tiers"][0]["spending_percentage"], 0.8)
        self.assertEqual(config["default_agent"], baseline["default_agent"])

    def test_smart_defaults_with_budget_and_dynamic_models_gives_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "model_services"):
            self.run_notebook(["mlflow/v1/chat/completions"], {"budget_id": "test-budget"})

    def test_smart_defaults_reads_new_budget_without_rerunning_setup(self):
        baseline = baseline_config()
        baseline["enabled_agents"][1]["config"]["models"] = {
            "model_services": ["system.ai.claude-haiku-4-5"],
        }
        smart_defaults_cell = next(cell for cell in SOURCE.split("# COMMAND ----------")
                                   if "\nsmart_defaults_config = None\n" in cell)
        with patch(__name__ + ".baseline_config", return_value=baseline):
            values = self.run_notebook(["mlflow/v1/chat/completions"])
            self.assertIsNone(values["smart_defaults_config"])
            # 予算を作成してパネルへ入力した後、3.1だけ再実行する。
            # 他のパラメータや初期設定セルは読み直さない。
            def read_budget_only(name):
                self.assertEqual(name, "budget_id")
                return "budget-created-after-setup"
            values["dbutils"].widgets.get.side_effect = read_budget_only
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(smart_defaults_cell, str(ROOT), "exec"), values)
        self.assertEqual(values["smart_defaults_config"]["smart_defaults"]["budget_id"],
                         "budget-created-after-setup")

    def test_reused_service_is_used_in_config_and_analysis_without_recreation(self):
        existing = "llmops-ai-governance-workshop.team.guardrail_demo_existing_user"
        # セクション1完了後の静的モデル一覧を公開済みの状態にする。
        baseline = baseline_config()
        baseline["enabled_agents"][1]["config"]["models"] = {
            "model_services": ["system.ai.claude-haiku-4-5"],
        }
        with patch(__name__ + ".baseline_config", return_value=baseline):
            values = self.run_notebook(["anthropic/v1/messages"], {"existing_service": existing})
        self.assertEqual(values["WORKSHOP_SERVICE"], existing)
        claude = next(a["config"] for a in values["phase2_config"]["enabled_agents"]
                      if a["agent"] == NAMESPACE["CLAUDE_AGENT"])
        self.assertIn(existing, claude["models"]["model_services"])
        for prompt in list(values["analysis_prompts"].values())[1:]:
            self.assertIn(existing, prompt)
            self.assertNotIn("coding_agent_first_last", prompt)

    def test_missing_service_does_not_create_or_register_it(self):
        # 新規作成前の全セル実行でも、GET以外を許可しないモックで完走する。
        values = self.run_notebook(["anthropic/v1/messages"], service_exists=False)
        self.assertIsNone(values["workshop_service"])
        self.assertFalse(values["can_use_in_claude"])
        self.assertIsNone(values["phase2_config"])

    def test_service_permission_error_is_not_treated_as_missing(self):
        with self.assertRaises(PermissionError):
            self.run_notebook(PermissionError("no EXECUTE"))

    def test_analysis_needs_no_table_name_and_only_generates_instructions(self):
        # run_notebookのモックは既存のGET以外を拒否。分析セルからSQLやAPIを実行しない。
        values = self.run_notebook(["mlflow/v1/chat/completions"], {
            "analysis_start_utc": "2026-01-01T00:00:00Z",
        })
        self.assertEqual(len(values["analysis_prompts"]), 4)
        widget_names = {call.args[0] for call in values["dbutils"].widgets.text.call_args_list}
        self.assertNotIn("trace_table", widget_names)
        discovery = list(values["analysis_prompts"].values())[0]
        self.assertIn("https://example.cloud.databricks.com", discovery)
        self.assertIn("複数の候補", discovery)
        for text in list(values["analysis_prompts"].values())[1:]:
            self.assertIn("この会話で確認した", text)
            self.assertIn("attributes:['enduser.id']::STRING = current_user()", text)
            self.assertIn("kind = 'SPAN_KIND_SERVER'", text)
            self.assertIn(values["WORKSHOP_SERVICE"], text)
            self.assertIn(values["analysis_end_utc"], text)


if __name__ == "__main__":
    unittest.main()
