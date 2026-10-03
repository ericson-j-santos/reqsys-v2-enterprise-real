import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "tools" / "teams-gateway-control-center-site-recovery"


def test_recovered_control_center_has_expected_identity_and_endpoint() -> None:
    html = (RECOVERY / "index.html").read_text(encoding="utf-8")

    assert "Teams Gateway Control Center" in html
    assert "/v1/teams-gateway/status" in html
    assert "amostras demonstrativas" in html


def test_recovery_metadata_is_fail_closed_about_provenance_and_runtime() -> None:
    metadata = json.loads((RECOVERY / "SOURCE-METADATA.json").read_text(encoding="utf-8"))

    assert metadata["artifact"] == "teams-gateway-control-center-site-recovery"
    assert metadata["recovery_status"] == "partial_source_recovery"
    assert metadata["source_project_uri"] == (
        "sites-project://appgprj_6a615cfc7c9881918dee3af3303d631a"
    )
    assert metadata["original_snapshot_status"] == "not_accessible_from_current_connection"
    assert metadata["safety"] == {
        "secrets_included": False,
        "runtime_changed": False,
        "deployment_performed": False,
        "production_touched": False,
    }
