from pathlib import Path

from scripts.validate_bacen_controls import resolve_evidence, validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def test_bacen02_and_bacen05_resolve_through_canonical_manifests():
    cases = {
        "BACEN-02": "artifacts/bacen/bacen-02-consolidated-readiness.json",
        "BACEN-05": "artifacts/bacen/bacen-05-consolidated-readiness.json",
    }

    for control_id, evidence_path in cases.items():
        resolution, findings = resolve_evidence(ROOT, control_id, evidence_path)
        assert findings == []
        assert resolution["resolution"] == "canonical_manifest"
        assert resolution["resolved_path"].startswith("governance/bacen/evidence/")


def test_bacen_gate_reduces_pending_materialization_without_promoting_partial_controls():
    report = validate(ROOT, MATRIX)
    resolutions = {
        item["control_id"]: item["resolution"]
        for item in report["evidence_resolution"]
    }

    assert report["result"] == "valid"
    assert resolutions["BACEN-02"] == "canonical_manifest"
    assert resolutions["BACEN-05"] == "canonical_manifest"
    assert report["summary"]["canonical_evidence_resolved"] >= 5
    assert report["summary"]["evidence_not_materialized"] == 2
    assert report["summary"]["implemented"] == 4
    assert report["summary"]["partial"] == 4
    assert report["summary"]["implemented_coverage_percent"] == 50.0
