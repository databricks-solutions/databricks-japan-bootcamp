import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app


class ConnectionConfigTests(unittest.TestCase):
    def test_pg_user_defaults_to_databricks_client_id(self):
        with patch.dict(os.environ, {"DATABRICKS_CLIENT_ID": "app-client-id"}, clear=True):
            self.assertEqual(app.pg_user(), "app-client-id")

    def test_explicit_pg_user_wins(self):
        with patch.dict(
            os.environ,
            {"PGUSER": "explicit-user", "DATABRICKS_CLIENT_ID": "app-client-id"},
            clear=True,
        ):
            self.assertEqual(app.pg_user(), "explicit-user")

    def test_connection_string_supplies_standard_connection_values(self):
        with patch.dict(
            os.environ,
            {
                "LAKEBASE_CONNECTION_STRING": (
                    "postgresql://ignored@example.test:5544/workshop?sslmode=verify-full"
                )
            },
            clear=True,
        ):
            self.assertEqual(app.pg_host(), "example.test")
            self.assertEqual(app.pg_port(), "5544")
            self.assertEqual(app.pg_dbname(), "workshop")
            self.assertEqual(app.pg_sslmode(), "verify-full")

    def test_app_resource_mode_uses_injected_pg_environment(self):
        with patch.dict(
            os.environ,
            {
                "LAKEBASE_CONNECTION_MODE": "app-resource",
                "PGHOST": "resource.example.test",
                "PGDATABASE": "databricks_postgres",
                "PGPORT": "5432",
                "PGSSLMODE": "require",
                "PGUSER": "app-client-id",
                "ENDPOINT_NAME": (
                    "projects/sample-project/branches/participant-a/endpoints/primary"
                ),
            },
            clear=True,
        ):
            self.assertEqual(app.connection_mode(), "app-resource")
            self.assertEqual(app.pg_host(), "resource.example.test")
            self.assertEqual(app.pg_user(), "app-client-id")

    def test_manual_connection_string_remains_supported(self):
        with patch.dict(
            os.environ,
            {
                "LAKEBASE_CONNECTION_STRING": (
                    "postgresql://ignored@manual.example.test/workshop?sslmode=require"
                ),
                "DATABRICKS_CLIENT_ID": "app-client-id",
                "ENDPOINT_NAME": (
                    "projects/sample-project/branches/participant-a/endpoints/primary"
                ),
            },
            clear=True,
        ):
            self.assertEqual(app.connection_mode(), "manual-connection-string")
            self.assertEqual(app.pg_host(), "manual.example.test")
            self.assertEqual(app.pg_user(), "app-client-id")

    def test_missing_endpoint_has_resource_specific_hint(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LAKEBASE_CONNECTION_MODE": "app-resource",
                "PGHOST": "resource.example.test",
                "PGUSER": "app-client-id",
            },
            clear=True,
        ):
            hint = app.config_hint()
            self.assertIsNotNone(hint)
            assert hint is not None
            self.assertIn("valueFrom: lakebase-demo", hint)


class DemoDataTests(unittest.TestCase):
    def test_sqlite_demo_data_is_visibly_distinct_from_lakebase_seed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = Path(temp_dir) / "demo.sqlite3"
            with patch.object(app, "SQLITE_PATH", sqlite_path):
                with patch.dict(os.environ, {}, clear=True):
                    app.init_local_db()
                    with app.sqlite_connect() as conn:
                        rows = conn.execute(
                            "SELECT id, title, customer FROM tickets ORDER BY id"
                        ).fetchall()

        self.assertEqual([row["id"] for row in rows], [101, 102, 103])
        self.assertTrue(all(row["title"].startswith("[DEMO]") for row in rows))
        self.assertTrue(all(row["customer"] == "Sample Company" for row in rows))


class InitializationHealthTests(unittest.TestCase):
    def setUp(self):
        self.original_init_ok = app._init_ok
        self.original_init_error = app._init_error

    def tearDown(self):
        app._init_ok = self.original_init_ok
        app._init_error = self.original_init_error

    def test_initialization_failure_is_recorded_without_crashing(self):
        with (
            patch.object(app, "using_postgres", return_value=True),
            patch.object(app, "init_db_enabled", return_value=True),
            patch.object(
                app,
                "pg_connect",
                side_effect=PermissionError("permission denied for schema public"),
            ),
        ):
            app.init_database()

        self.assertFalse(app._init_ok)
        self.assertEqual(app._init_error, "permission denied for schema public")

    def test_health_reports_connected_but_initialization_failed(self):
        app._init_ok = False
        app._init_error = "permission denied for schema public"
        connection = MagicMock()

        with (
            patch.dict(
                os.environ,
                {
                    "PGHOST": "example.test",
                    "PGUSER": "app-client-id",
                    "ENDPOINT_NAME": (
                        "projects/sample-project/branches/participant-a/endpoints/primary"
                    ),
                },
                clear=True,
            ),
            patch.object(app, "pg_connect", return_value=connection),
        ):
            payload = app.health_payload()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["database"], "lakebase")
        self.assertEqual(payload["branch"], "participant-a")
        self.assertFalse(payload["init_ok"])
        self.assertEqual(payload["init_error"], "permission denied for schema public")


class RuntimeConfigTests(unittest.TestCase):
    def test_main_prefers_databricks_app_port(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"DATABRICKS_APP_PORT": "4321", "PORT": "9999"},
                clear=True,
            ),
            patch.object(app, "init_database"),
            patch.object(app, "ThreadingHTTPServer") as server_class,
        ):
            app.main()

        server_class.assert_called_once_with(("0.0.0.0", 4321), app.AppHandler)
        server_class.return_value.serve_forever.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
