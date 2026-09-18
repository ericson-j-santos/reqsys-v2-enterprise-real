import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.consolidate_bacen_audit_evidence import consolidate, index_evidence, sha256_of

MATRIX = """
schema_version: 1.2.0
controls:
  - id: BACEN-01
    domain: governance
    title: Example
    criticality: critical
    owner: SECURITY
    evidence: docs/policy.md
    status: partial
    review_cycle_days: 365
  - id: BACEN-02
    domain: audit
    title: Example audit
    criticality: high
    owner: SECURITY
    evidence: artifacts/bacen/bacen-02-evidence.json
    status: implemented
    review_cycle_days: 90
  - id: BACEN-03
    domain: third_party
    title: Example gap
    criticality: high
    owner: AI_GOVERNOR
    evidence: governance/bacen/missing.yaml
    status: gap
    review_cycle_days: 180
"""


class ConsolidateTests(unittest.TestCase):
    def test_covers_controls_via_indexed_entry_or_materialized_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "policy.md").write_text("policy", encoding="utf-8")

            evidence_dir = root / "artifacts" / "bacen"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "bacen-02-evidence.json").write_text(
                json.dumps({"control_id": "BACEN-02", "schema_version": "1.0.0"}), encoding="utf-8"
            )

            matrix_path = root / "matrix.yaml"
            matrix_path.write_text(MATRIX, encoding="utf-8")

            report = consolidate(root, matrix_path, evidence_dir)

            self.assertEqual(report["result"], "valid")
            self.assertIn("BACEN-01", report["summary"]["controls_covered"])
            self.assertIn("BACEN-02", report["summary"]["controls_covered"])
            self.assertNotIn("BACEN-03", report["summary"]["controls_covered"])
            self.assertNotIn("BACEN-03", report["summary"]["controls_uncovered"])

    def test_flags_tracked_control_without_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_dir = root / "artifacts" / "bacen"
            evidence_dir.mkdir(parents=True)

            matrix_path = root / "matrix.yaml"
            matrix_path.write_text(MATRIX, encoding="utf-8")

            report = consolidate(root, matrix_path, evidence_dir)

            self.assertEqual(report["result"], "invalid")
            self.assertIn("BACEN-01", report["summary"]["controls_uncovered"])
            self.assertIn("BACEN-02", report["summary"]["controls_uncovered"])

    def test_index_evidence_computes_sha256(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_dir = root / "artifacts" / "bacen"
            evidence_dir.mkdir(parents=True)
            evidence_file = evidence_dir / "sample.json"
            evidence_file.write_text(json.dumps({"control_id": "BACEN-01"}), encoding="utf-8")

            entries = index_evidence(evidence_dir)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["sha256"], sha256_of(evidence_file))
            self.assertEqual(entries[0]["control_id"], "BACEN-01")


if __name__ == "__main__":
    unittest.main()
