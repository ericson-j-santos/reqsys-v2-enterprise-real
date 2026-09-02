import copy
import unittest
from pathlib import Path

import yaml

from scripts.validate_bacen_normative_axis import (
    EXPECTED_CODES,
    EXTENDED_CODES,
    MINIMUM_CODES,
    load_obligation_sets,
    normalized_text_sha256,
    validate,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE_V2 = ROOT / "governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml"


def load_v2():
    return yaml.safe_load(BASELINE_V2.read_text(encoding="utf-8"))


def load_obligations(payload):
    obligations, errors = load_obligation_sets(ROOT, payload["normative_baseline"])
    if errors:
        raise AssertionError(errors)
    return obligations


class BacenNormativeAxisTests(unittest.TestCase):
    def test_v2_models_57_obligations_as_not_evaluated(self):
        report = validate(BASELINE_V2)
        self.assertEqual(report["result"], "valid_with_pending_items")
        self.assertEqual(report["summary"]["obligations_modeled"], 57)
        self.assertEqual(report["summary"]["minimum_controls"], 14)
        self.assertEqual(report["summary"]["extended_obligations"], 43)
        self.assertEqual(report["summary"]["expected_total"], len(EXPECTED_CODES))
        self.assertEqual(report["summary"]["derived_nao_avaliado"], 57)
        self.assertTrue(all(state == "nao_avaliado" for state in report["derived_states"].values()))
        self.assertFalse(report["summary"]["coverage_scalar_published"])

    def test_expected_sets_are_stable(self):
        self.assertEqual(len(MINIMUM_CODES), 14)
        self.assertEqual(len(EXTENDED_CODES), 43)
        self.assertIn("CMN4893-ART3A-I-A", EXTENDED_CODES)
        self.assertIn("CMN4893-ART22A-I", EXTENDED_CODES)
        self.assertIn("CMN4893-ART23-X", EXTENDED_CODES)

    def test_status_cannot_be_declared_manually(self):
        payload = load_v2()
        obligations = load_obligations(payload)
        obligations[0]["status"] = "evidenciado"
        report = validate_payload(payload, obligations)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("status não pode ser campo de entrada" in e for e in report["errors"]))

    def test_missing_extended_obligation_is_invalid(self):
        payload = load_v2()
        obligations = load_obligations(payload)
        obligations = [o for o in obligations if o["code"] != "CMN4893-ART3A-I-F"]
        report = validate_payload(payload, obligations)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("obrigações normativas esperadas ausentes" in e for e in report["errors"]))

    def test_raw_pdf_hash_scope_is_rejected(self):
        payload = load_v2()
        obligations = load_obligations(payload)
        payload["normative_baseline"]["referenced_documents"][0]["hash_scope"] = "raw_file"
        report = validate_payload(payload, obligations)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("hash de PDF bruto é proibido" in e for e in report["errors"]))

    def test_captured_hash_requires_64_lowercase_hex(self):
        payload = load_v2()
        obligations = load_obligations(payload)
        doc = payload["normative_baseline"]["referenced_documents"][0]
        doc["hash_state"] = "captured"
        doc["content_sha256"] = "ABC"
        report = validate_payload(payload, obligations)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("64 hex" in e for e in report["errors"]))

    def test_normalized_hash_ignores_page_markers_and_repeated_headers(self):
        base = "Manual de Segurança do SFN\nManual de Segurança do SFN\nManual de Segurança do SFN\nConteúdo   crítico\nPágina 1/3\nOutro conteúdo\n"
        noisy = "Manual de Segurança do SFN\r\nManual de Segurança do SFN\r\nManual de Segurança do SFN\r\nConteúdo crítico\r\n2/3\r\nOutro   conteúdo\r\n"
        self.assertEqual(normalized_text_sha256(base), normalized_text_sha256(noisy))

    def test_not_applicable_requires_named_decision(self):
        payload = load_v2()
        obligations = load_obligations(payload)
        payload["applicability"]["decision"] = "not_applicable"
        payload["applicability"]["decided_by"] = None
        payload["applicability"]["decided_at"] = None
        report = validate_payload(payload, obligations)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("not_applicable exige" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
