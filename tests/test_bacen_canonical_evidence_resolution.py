from pathlib import Path

from scripts.validate_bacen_controls import resolve_evidence, validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def test_bacen01_resolves_declared_artifact_through_canonical_manifest():
    resolution, findings = resolve_evidence(
        ROOT,
        "BACEN-01",
        "artifacts/bacen/bacen-01-policy-governance-attestation.json",
    )
    assert findings == []
    assert resolution["resolution"] == "canonical_manifest"
    assert resolution["resolved_path"] == (
        "governance/bacen/evidence/"
        "bacen-01-policy-governance-attestation.manifest.yaml"
    )


def test_bacen_gate_reports_one_canonical_resolution_without_false_promotion():
    report = validate(ROOT, MATRIX)
    bacen01 = next(
        item for item in report["evidence_resolution"] if item["control_id"] == "BACEN-01"
    )
    assert report["result"] == "valid"
    assert report["summary"]["canonical_evidence_resolved"] >= 1
    assert bacen01["resolution"] == "canonical_manifest"
    assert report["summary"]["implemented"] == 4
    assert report["summary"]["partial"] == 4
    assert not any("BACEN-01: evidência ainda não materializada" in item for item in report["warnings"])
