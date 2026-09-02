import copy
import unittest
from pathlib import Path

import yaml

from scripts.validate_bacen_normative_axis import EXPECTED_CODES, validate_payload

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "governance/bacen/normative/NORMATIVE-BASELINE.yaml"


def load_payload():
    return yaml.safe_load(BASELINE.read_text(encoding="utf-8"))


class BacenNormativeAxisTests(unittest.TestCase):
    def test_initial_baseline_models_all_14_minimum_controls_as_not_evaluated(self):
        report = validate_payload(load_payload())
        self.assertEqual(report["result"], "valid_with_pending_items")
        self.assertEqual(report["summary"]["obligations_modeled"], 14)
        self.assertEqual(report["summary"]["required_minimum_controls"], 14)
        self.assertEqual(report["summary"]["derived_nao_avaliado"], 14)
        self.assertEqual(set(report["derived_states"]), set(EXPECTED_CODES))
        self.assertTrue(all(state == "nao_avaliado" for state in report["derived_states"].values()))
        self.assertFalse(report["summary"]["coverage_scalar_published"])

    def test_status_cannot_be_declared_manually(self):
        payload = load_payload()
        payload["obligations"][0]["status"] = "implementado"
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("status não pode ser campo de entrada" in error for error in report["errors"]))

    def test_missing_minimum_control_is_invalid(self):
        payload = load_payload()
        payload["obligations"] = payload["obligations"][:-1]
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("controles mínimos normativos ausentes" in error for error in report["errors"]))

    def test_duplicate_uid_is_invalid(self):
        payload = load_payload()
        payload["obligations"][1]["uid"] = payload["obligations"][0]["uid"]
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("uid duplicado" in error for error in report["errors"]))

    def test_applicable_obligation_requires_mapping(self):
        payload = load_payload()
        payload["applicability"]["decision"] = "applicable"
        payload["applicability"]["decided_by"] = "SECURITY"
        payload["applicability"]["decided_at"] = "2026-09-02"
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("obrigação aplicável sem vínculo" in error for error in report["errors"]))

    def test_not_applicable_requires_named_decision(self):
        payload = load_payload()
        payload["applicability"]["decision"] = "not_applicable"
        payload["applicability"]["decided_by"] = None
        payload["applicability"]["decided_at"] = None
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("not_applicable exige" in error for error in report["errors"]))

    def test_assessment_claim_requires_schema_evolution(self):
        payload = load_payload()
        payload["obligations"][0]["assessment"] = {"implementation_complete": True}
        report = validate_payload(payload)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(any("assessment não nulo" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
