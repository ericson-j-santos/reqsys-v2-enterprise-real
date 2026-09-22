import unittest
from pathlib import Path

from scripts.assess_bacen_obligations_simulation import (
    DEFAULT_BASELINES,
    DEFAULT_EVIDENCE,
    EXPECTED_TOTAL,
    assess,
    load_yaml,
)

ROOT = Path(__file__).resolve().parents[1]


class AssessBacenObligationsSimulationTests(unittest.TestCase):
    def test_default_baselines_compose_all_57_obligations(self):
        baselines = [load_yaml(ROOT / path) for path in DEFAULT_BASELINES]
        evidence = load_yaml(ROOT / DEFAULT_EVIDENCE)

        result = assess(baselines, evidence)
        codes = {item["code"] for item in result["obligations"]}

        self.assertEqual(result["total"], EXPECTED_TOTAL)
        self.assertEqual(result["total"], 57)
        self.assertEqual(result["conditional"], 13)
        self.assertIn("CMN4893-ART3-P2-I", codes)
        self.assertIn("CMN4893-ART3A-I-A", codes)
        self.assertIn("CMN4893-ART23-X", codes)

    def test_single_extended_baseline_remains_incomplete(self):
        extended = load_yaml(ROOT / DEFAULT_BASELINES[1])
        result = assess(extended, {})

        self.assertEqual(result["total"], 43)
        self.assertNotEqual(result["total"], EXPECTED_TOTAL)


if __name__ == "__main__":
    unittest.main()
