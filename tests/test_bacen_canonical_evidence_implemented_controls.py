from pathlib import Path

from scripts.validate_bacen_controls import resolve_evidence, validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def test_bacen03_and_bacen07_resolve_through_canonical_manifests():
    cases = {
        "BACEN-03": "artifacts/bacen/bacen-03-incident-exercise-evidence.json",
        "BACEN-07": "artifacts/bacen/bacen-07-audit-evidence-index.json",
    }

    for control_id, evidence_path in cases.items():
        resolution, findings = resolve_evidence(ROOT, control_id, evidence_path)
        assert findings == []
        assert resolution["resolution"] == "canonical_manifest"
        assert resolution["resolved_path"].startswith("governance/bacen/evidence/")


def test_bacen_gate_reduces_not_materialized_evidence_without_status_promotion():
    report = validate(ROOT, MATRIX)

    resolutions = {
        item["control_id"]: item["resolution"]
        for item in report["evidence_resolution"]
    }

    assert report["result"] == "valid"
    assert resolutions["BACEN-01"] == "canonical_manifest"
    assert resolutions["BACEN-03"] == "canonical_manifest"
    assert resolutions["BACEN-07"] == "canonical_manifest"
    assert report["summary"]["canonical_evidence_resolved"] >= 3
    assert report["summary"]["evidence_not_materialized"] == 4
    assert report["summary"]["implemented"] == 4
    assert report["summary"]["partial"] == 4
    assert report["summary"]["implemented_coverage_percent"] == 50.0
