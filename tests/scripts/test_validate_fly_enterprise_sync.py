import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_fly_enterprise_sync import (  # noqa: E402
    DEFAULT_MANIFEST,
    validate,
)


def test_validate_fly_enterprise_sync_accepts_permanent_retirement():
    exit_code, payload = validate(DEFAULT_MANIFEST)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "retirement_evidence"
    assert payload["retirement"]["status"] == "PERMANENTLY_RETIRED"
    assert payload["promotion_order"] == ["dev", "hml", "prod"]
    assert [item["api_app"] for item in payload["environments"]] == [
        "reqsys-api-dev",
        "reqsys-api-stg",
        "reqsys-api",
    ]
    assert payload["errors"] == []
    assert all(item["status"] == "PERMANENTLY_RETIRED" for item in payload["environments"])
    assert all(item["referenced_configs_absent"] for item in payload["environments"])


def test_validate_fly_enterprise_sync_requires_approval_for_hml_and_prod():
    exit_code, payload = validate(DEFAULT_MANIFEST)

    assert exit_code == 0
    approvals = {item["environment"]: item["approval_required"] for item in payload["environments"]}
    assert approvals == {"dev": False, "hml": True, "prod": True}


def test_validate_fly_enterprise_sync_never_accepts_active_mode(tmp_path):
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    manifest.pop("retirement")
    candidate = tmp_path / "fly-environments.json"
    candidate.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code, payload = validate(candidate)

    assert exit_code == 1
    assert payload["ok"] is False
    assert any("PERMANENTLY_RETIRED" in error for error in payload["errors"])
