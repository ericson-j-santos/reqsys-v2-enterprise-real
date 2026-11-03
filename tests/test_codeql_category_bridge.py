"""Regressão da paridade das categorias de SARIF CodeQL sem falsos resultados."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.codeql_category_bridge import CategoryBridgeError, stage_codeql_categories


class CodeQLCategoryBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "sarif"
        self.output = self.root / "publication"
        self.receipt = self.root / "audit" / "receipt.json"
        self.languages = ["python", "javascript-typescript"]

    def create(self, language: str, *, category: str | None = None, results=None):
        payload = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "version": "2.0"}},
                    "automationDetails": {"id": category or f"/language:{language}/"},
                    "results": results if results is not None else [
                        {"ruleId": "py/sql-injection", "partialFingerprints": {"hash": "abcd"}}
                    ],
                }
            ],
        }
        file = self.source / language / "processed" / "upload.sarif"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def both(self):
        return {language: self.create(language) for language in self.languages}

    def run_bridge(self, languages=None):
        return stage_codeql_categories(
            self.source, self.output,
            self.languages if languages is None else languages,
            self.receipt,
        )

    def test_compatibility_aliases_preserve_real_findings_and_tool(self):
        originals = self.both()
        receipt = self.run_bridge()
        self.assertEqual(receipt["category_count"], 4)
        self.assertEqual(receipt["source_analysis_count"], 2)
        self.assertFalse(receipt["deletion_performed"])
        self.assertTrue(receipt["legacy_compatibility_only"])
        for language in self.languages:
            primary = json.loads((self.output / f"{language}.sarif").read_text())
            legacy = json.loads((self.output / f"legacy-{language}.sarif").read_text())
            self.assertEqual(primary, originals[language])
            self.assertEqual(legacy["runs"][0]["automationDetails"]["id"], f"language:{language}/")
            self.assertEqual(legacy["runs"][0]["automationDetails"]["id"].rsplit("/", 1)[0], f"language:{language}")
            self.assertEqual(legacy["runs"][0]["results"], originals[language]["runs"][0]["results"])
            self.assertEqual(legacy["runs"][0]["tool"], originals[language]["runs"][0]["tool"])
        self.assertEqual(json.loads(self.receipt.read_text()), receipt)
        self.assertTrue(all(item["finding_mutations"] == 0 for item in receipt["categories"]))

    def test_repeat_in_isolated_workspace_is_deterministic(self):
        self.both()
        self.run_bridge()
        first = {p.name: p.read_bytes() for p in self.output.glob("*.sarif")}
        for p in self.output.glob("*.sarif"):
            p.unlink()
        self.run_bridge()
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.output.glob("*.sarif")})

    def test_reject_missing_language(self):
        self.create("python")
        with self.assertRaisesRegex(CategoryBridgeError, "Análises ausentes"):
            self.run_bridge()

    def test_reject_duplicate_same_category(self):
        self.both()
        self.create("additional", category="/language:python/")
        with self.assertRaisesRegex(CategoryBridgeError, "duplicada"):
            self.run_bridge()

    def test_reject_unexpected_legacy_input(self):
        self.both()
        self.create("javascript-typescript", category="language:javascript-typescript")
        with self.assertRaisesRegex(CategoryBridgeError, "inesperada"):
            self.run_bridge()

    def test_reject_invalid_json(self):
        self.both()
        (self.source / "python" / "processed" / "upload.sarif").write_text("not-json")
        with self.assertRaisesRegex(CategoryBridgeError, "SARIF inválido"):
            self.run_bridge()

    def test_reject_unexpected_source_tool(self):
        self.both()
        file = self.source / "python" / "processed" / "upload.sarif"
        payload = json.loads(file.read_text())
        payload["runs"][0]["tool"]["driver"]["name"] = "FauxQL"
        file.write_text(json.dumps(payload))
        with self.assertRaisesRegex(CategoryBridgeError, "não é CodeQL"):
            self.run_bridge()

    def test_reject_incomplete_language_selection(self):
        self.both()
        with self.assertRaisesRegex(CategoryBridgeError, "ambas as linguagens"):
            self.run_bridge(["python"])

    def test_reject_replay_into_stale_output(self):
        self.both()
        self.run_bridge()
        with self.assertRaisesRegex(CategoryBridgeError, "não está vazio"):
            self.run_bridge()

    def test_reject_receipt_in_sarif_directory(self):
        self.both()
        with self.assertRaisesRegex(CategoryBridgeError, "Recibo deve"):
            stage_codeql_categories(self.source, self.output, self.languages, self.output / "receipt.json")


if __name__ == "__main__":
    unittest.main()
