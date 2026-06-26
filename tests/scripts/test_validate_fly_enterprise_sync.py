from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_fly_enterprise_sync import DEFAULT_MANIFEST, validate


def test_validate_fly_enterprise_sync_manifest_passes():
    exit_code, payload = validate(DEFAULT_MANIFEST)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["promotion_order"] == ["dev", "hml", "prod"]
    assert [item["api_app"] for item in payload["environments"]] == [
        "reqsys-api-dev",
        "reqsys-api-hml",
        "reqsys-api-prod",
    ]
    assert payload["errors"] == []


def test_validate_fly_enterprise_sync_requires_approval_for_hml_and_prod():
    exit_code, payload = validate(DEFAULT_MANIFEST)

    assert exit_code == 0
    approvals = {item["environment"]: item["approval_required"] for item in payload["environments"]}
    assert approvals == {"dev": False, "hml": True, "prod": True}
