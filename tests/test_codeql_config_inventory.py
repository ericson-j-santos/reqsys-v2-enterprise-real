"""Testes de auditoria CodeQL API sem efeitos colaterais nem token real."""

import json
import subprocess
import unittest

from scripts.codeql_config_inventory import CodeQLInventoryError, inventory


REPO = "user/repo"
REF = "refs/pull/3127/merge"


def response_for(records):
    def runner(command, **kwargs):
        url = command[-1]
        label = "main" if "refs%2Fheads%2Fmain" in url else "pr"
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(records[label]), stderr=""
        )
    return runner


def record(category, *, key=".github/workflows/security-specialized-scanners.yml:codeql"):
    return {"analysis_key": key, "category": category, "tool": {"name": "CodeQL"},
            "ref": "refs/heads/main", "commit_sha": "a" * 40, "id": 123, "results_count": 1}


class CodeQLConfigInventoryTests(unittest.TestCase):
    def test_matching_configuration_identities(self):
        records = [record("/language:python/"), record("/language:javascript-typescript/")]
        result = inventory(REPO, REF, runner=response_for({"main": records, "pr": records}))
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["missing_main_configurations_in_pr"], [])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["deletions"], 0)

    def test_same_category_different_analysis_key_is_not_match(self):
        a = record("language:python", key=".github/workflows/security-specialized-scanners.yml:codeql")
        b = record("language:python", key=".github/workflows/security-specialized-scanners.yml:codeql-generate")
        result = inventory(REPO, REF, runner=response_for({"main": [a], "pr": [b]}))
        self.assertEqual(result["status"], "incomplete_or_mismatch")
        self.assertEqual(result["missing_main_configurations_in_pr"], [
            {"analysis_key": a["analysis_key"], "category": "language:python"}
        ])

    def test_no_analysis_does_not_falsely_succeed(self):
        result = inventory(REPO, REF, runner=response_for({"main": [], "pr": []}))
        self.assertEqual(result["status"], "incomplete_or_mismatch")
        self.assertEqual(len(result["reports"]["main"]["configurations"]), 0)

    def test_malformed_api_rejected(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="{", stderr="")
        with self.assertRaises(CodeQLInventoryError):
            inventory(REPO, REF, runner=runner)

    def test_permanent_api_failure_rejected_without_retry(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="HTTP 403")
        with self.assertRaisesRegex(CodeQLInventoryError, "API Code Scanning indisponível"):
            inventory(REPO, REF, runner=runner)

    def test_invalid_ref_rejected(self):
        with self.assertRaises(ValueError):
            inventory(REPO, "refs/heads/main")

    def test_page_budget_rejects_incomplete_inventory(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps([record("/language:python/")] * 100), stderr="")
        result = inventory(REPO, REF, runner=runner, max_pages=1)
        self.assertEqual(result["status"], "incomplete_or_mismatch")
        self.assertFalse(result["reports"]["main"]["complete"])

    def test_timeout_fails_closed(self):
        def runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, timeout=10)
        with self.assertRaisesRegex(CodeQLInventoryError, "Timeout"):
            inventory(REPO, REF, runner=runner)


if __name__ == "__main__":
    unittest.main()
