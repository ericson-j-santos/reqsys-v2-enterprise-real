from pathlib import Path

from scripts.validate_bacen_controls import resolve_evidence, validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def test_bacen08_resolves_through_canonical_manifest_without_false_governance_promotion():
    resolution, findings = resolve_evidence(
        ROOT,
        "BACEN-08",
        "artifacts/bacen/bacen-08-executive-readiness.json",
    )
    assert findings == []
    assert resolution["resolution"] == "canonical_manifest"
    assert resolution["resolved_path"] == (
        "governance/bacen/evidence/bacen-08-executive-readiness.manifest.yaml"
    )


def test_bacen_gate_leaves_only_bacen04_not_materialized_and_preserves_statuses():
    report = validate(ROOT, MATRIX)
    resolutions = {
        item["control_id"]: item["resolution"]
        for item in report["evidence_resolution"]
    }

    assert report["result"] == "valid"
    assert resolutions["BACEN-08"] == "canonical_manifest"
    assert report["summary"]["canonical_evidence_resolved"] >= 6
    assert report["summary"]["evidence_not_materialized"] == 1
    assert resolutions["BACEN-04"] == "not_materialized"
    assert report["summary"]["implemented"] == 4
    assert report["summary"]["partial"] == 4
    assert report["summary"]["implemented_coverage_percent"] == 50.0
