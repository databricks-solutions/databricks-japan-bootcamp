import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP_NOTEBOOK = ROOT / "notebooks" / "facilitator_setup.py"


def embedded_sql(name: str) -> str:
    source = SETUP_NOTEBOOK.read_text(encoding="utf-8")
    match = re.search(rf'^{name} = """\n(.*?)"""', source, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"{name} is not defined in {SETUP_NOTEBOOK.name}")
    return match.group(1)


class FacilitatorSetupNotebookTests(unittest.TestCase):
    def test_schema_matches_postgres_schema_file(self) -> None:
        expected = (ROOT / "sql" / "schema.postgres.sql").read_text(encoding="utf-8")
        self.assertEqual(embedded_sql("SCHEMA_SQL"), expected)

    def test_seed_matches_postgres_seed_file(self) -> None:
        expected = (ROOT / "sql" / "seed.postgres.sql").read_text(encoding="utf-8")
        self.assertEqual(embedded_sql("SEED_SQL"), expected)

    def test_resource_key_matches_app_yaml(self) -> None:
        app_yaml = (ROOT / "app.yaml").read_text(encoding="utf-8")
        notebook = SETUP_NOTEBOOK.read_text(encoding="utf-8")
        self.assertIn('valueFrom: "lakebase-demo"', app_yaml)
        self.assertIn("Resource key: lakebase-demo", notebook)


if __name__ == "__main__":
    unittest.main()
