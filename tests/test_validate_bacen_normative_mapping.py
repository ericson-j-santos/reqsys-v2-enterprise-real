from pathlib import Path
import unittest

from scripts.validate_bacen_normative_axis import EXPECTED_CODES
from scripts.validate_bacen_normative_mapping import validate_mapping

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml"


class BacenNormativeMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = validate_mapping(ROOT, BASELINE)

    def test_repository_mapping_is_valid(self) -> None:
        self.assertEqual("valid", self.report["result"], self.report.get("errors"))

    def test_all_57_obligations_are_mapped(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(57, len(EXPECTED_CODES))
        self.assertEqual(57, summary["expected_obligations"])
        self.assertEqual(57, summary["mapped_obligations"])

    def test_all_macrocontrols_are_referenced(self) -> None:
        self.assertEqual(8, self.report["summary"]["macrocontrols_referenced"])

    def test_mapping_does_not_promote_evidence_or_assessment(self) -> None:
        summary = self.report["summary"]
        self.assertFalse(summary["assessment_promotion"])
        self.assertFalse(summary["evidence_claim"])

    def test_every_obligation_has_adr_and_pdr_link(self) -> None:
        links = self.report["effective_design_links"]
        self.assertEqual(set(EXPECTED_CODES), set(links))
        for code, refs in links.items():
            self.assertTrue(refs["adr_refs"], code)
            self.assertTrue(refs["pdr_refs"], code)


if __name__ == "__main__":
    unittest.main()
