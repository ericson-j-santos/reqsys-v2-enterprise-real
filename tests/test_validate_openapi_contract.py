from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_openapi_contract import validate_contract


def test_openapi_contract_validation_passes_for_current_contract() -> None:
    report = validate_contract(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json"))

    assert report["status"] == "passed"
    assert report["summary"]["valid"] is True
    assert report["summary"]["openapi_version"].startswith("3.")
    assert report["errors"] == []


def test_openapi_contract_validation_fails_when_required_path_missing(tmp_path: Path) -> None:
    contract = json.loads(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json").read_text(encoding="utf-8"))
    contract["paths"].pop("/api/requisitos/{id}", None)
    candidate = tmp_path / "openapi.json"
    candidate.write_text(json.dumps(contract), encoding="utf-8")

    report = validate_contract(candidate)

    assert report["status"] == "failed"
    assert "required_path_missing:/api/requisitos/{id}" in report["errors"]


def test_openapi_contract_validation_fails_on_invalid_json(tmp_path: Path) -> None:
    candidate = tmp_path / "openapi.json"
    candidate.write_text("{invalid-json", encoding="utf-8")

    report = validate_contract(candidate)

    assert report["status"] == "failed"
    assert report["errors"]
    assert report["errors"][0].startswith("json_parse_failed")
