from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "kindle_knowledge_local_cache.py"
WORKFLOW = ROOT / ".github" / "workflows" / "kindle-knowledge-local-cache.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

SPEC = importlib.util.spec_from_file_location("kindle_knowledge_local_cache", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class KindleKnowledgeLocalCacheTests(unittest.TestCase):
    def test_query_bundle_has_seven_statements(self) -> None:
        sql = mod.render_sql()
        self.assertEqual(7, len(mod.QUERIES))
        self.assertEqual(7, sql.count(";"))
        self.assertEqual([], mod.validate_queries(sql))

    def test_negative_query_validation_detects_missing_token(self) -> None:
        sql = mod.render_sql().replace("stddev_pop", "stddev_removed", 1)
        errors = mod.validate_queries(sql)
        self.assertTrue(any("stddev_pop" in error for error in errors))

    def test_output_root_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(mod.MaterializeError, "output_root não autorizado"):
            mod.validate_output_root(Path("C:/tmp/kindle-invalid"))

    def test_host_guard_rejects_unapproved_expected_host(self) -> None:
        with self.assertRaisesRegex(mod.MaterializeError, "não autorizado"):
            mod.validate_host("OTHER-HOST")

    def test_workflow_uses_both_self_hosted_hosts_and_schedule(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("schedule:", raw)
        self.assertIn("cron: '15 11 * * *'", raw)
        self.assertIn("runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]", raw)
        self.assertIn("runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]", raw)
        self.assertIn("MATERIALIZE-KINDLE-QUERIES", raw)
        self.assertIn("C:\\dev\\chatgpt-workers\\kindle-knowledge-local", raw)
        self.assertNotIn("secrets.", raw)

    def test_workflow_is_allowlisted(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn(
            ".github/workflows/kindle-knowledge-local-cache.yml",
            policy["approved_workflows"],
        )

    def test_script_never_reads_credentials(self) -> None:
        raw = SCRIPT.read_text(encoding="utf-8").casefold()
        self.assertNotIn("client_secret", raw)
        self.assertNotIn("access_token", raw)
        self.assertNotIn("token.json", raw)
        self.assertNotIn("refresh_token", raw)


if __name__ == "__main__":
    unittest.main()
