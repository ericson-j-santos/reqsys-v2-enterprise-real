import copy
import unittest
from unittest.mock import patch

import scripts.validate_bacen_structural_gate as gate


class StructuralGateTests(unittest.TestCase):
    def setUp(self):
        self.base = gate.load_yaml(gate.BASELINE)
        self.extended = gate.load_yaml(gate.EXTENDED)
        self.evidence = gate.load_yaml(gate.EVIDENCE_MODEL)

    def run_with(self, base=None, extended=None, evidence=None):
        payloads = [base or self.base, extended or self.extended, evidence or self.evidence]
        with patch.object(gate, "load_yaml", side_effect=payloads):
            return gate.validate()

    def test_current_repository_is_valid(self):
        result = gate.validate()
        self.assertEqual("valid", result["result"])
        self.assertEqual(57, result["obligations"])
        self.assertEqual(57, result["unique_uids"])
        self.assertFalse(result["coverage_scalar_published"])

    def test_duplicate_uid_is_rejected(self):
        extended = copy.deepcopy(self.extended)
        extended["obligations"][1]["uid"] = extended["obligations"][0]["uid"]
        result = self.run_with(extended=extended)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any("duplicado" in e for e in result["errors"]))

    def test_manual_status_is_rejected(self):
        base = copy.deepcopy(self.base)
        base["obligations"][0]["status"] = "evidenciado"
        result = self.run_with(base=base)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any("status manual" in e for e in result["errors"]))

    def test_not_applicable_requires_complete_decision(self):
        base = copy.deepcopy(self.base)
        base["applicability"]["decision"] = "not_applicable"
        base["applicability"]["decided_by"] = None
        result = self.run_with(base=base)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any("decided_by" in e for e in result["errors"]))

    def test_applicable_requires_mapping(self):
        base = copy.deepcopy(self.base)
        base["applicability"]["decision"] = "applicable"
        result = self.run_with(base=base)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any(e.startswith("R3:") for e in result["errors"]))

    def test_scalar_coverage_is_rejected(self):
        base = copy.deepcopy(self.base)
        base["regulatory_coverage"] = 0.5
        result = self.run_with(base=base)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any(e.startswith("R5:") for e in result["errors"]))

    def test_evidence_contract_must_forbid_status(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["evidence_contract"]["forbidden"] = []
        result = self.run_with(evidence=evidence)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any(e.startswith("R9:") for e in result["errors"]))

    def test_event_at_must_drive_time(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["invariants"]["temporal_origin"] = "collected_at"
        result = self.run_with(evidence=evidence)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any("temporal_origin" in e for e in result["errors"]))

    def test_masking_and_custody_are_present(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["evidence_contract"]["optional"] = [
            item for item in evidence["evidence_contract"]["optional"] if item not in {"masking", "custody_ref"}
        ]
        result = self.run_with(evidence=evidence)
        self.assertEqual("invalid", result["result"])
        self.assertTrue(any(e.startswith("R14:") or e.startswith("R13/R14:") for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
