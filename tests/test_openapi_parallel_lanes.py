from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_postman_from_openapi import build_collection, _load_contract
from scripts.validate_openapi_routes_drift import GOVERNED_PATHS, analyze_drift, _normalize_path


def test_openapi_contract_validation_passes_for_current_contract() -> None:
    from scripts.validate_openapi_contract import validate_contract

    report = validate_contract(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json"))

    assert report["status"] == "passed"
    assert report["summary"]["valid"] is True
    assert report["summary"]["openapi_version"].startswith("3.")
    assert report["errors"] == []


def test_openapi_contract_validation_fails_when_required_path_missing(tmp_path: Path) -> None:
    from scripts.validate_openapi_contract import validate_contract

    contract = json.loads(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json").read_text(encoding="utf-8"))
    contract["paths"].pop("/api/requisitos/{id}", None)
    candidate = tmp_path / "openapi.json"
    candidate.write_text(json.dumps(contract), encoding="utf-8")

    report = validate_contract(candidate)

    assert report["status"] == "failed"
    assert "required_path_missing:/api/requisitos/{id}" in report["errors"]


def test_openapi_contract_validation_fails_on_invalid_json(tmp_path: Path) -> None:
    from scripts.validate_openapi_contract import validate_contract

    candidate = tmp_path / "openapi.json"
    candidate.write_text("{invalid-json", encoding="utf-8")

    report = validate_contract(candidate)

    assert report["status"] == "failed"
    assert report["errors"]
    assert report["errors"][0].startswith("json_parse_failed")


def test_postman_collection_generation_includes_governed_paths() -> None:
    contract = _load_contract(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json"))
    collection = build_collection(contract, "docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json")

    names = {folder["name"] for folder in collection["item"]}
    assert "/api/runtime/health" in names
    assert "/api/runtime/dashboard" in names
    assert "/api/requisitos" in names


def test_openapi_routes_drift_passes_for_current_contract() -> None:
    report = analyze_drift(Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json"))

    assert report["status"] == "passed", report["errors"]
    assert report["summary"]["missing_in_openapi"] == 0
    assert report["summary"]["missing_in_backend"] == 0


def test_path_param_normalization_treats_id_and_identificador_as_equivalent() -> None:
    assert _normalize_path("/api/requisitos/{id}") == _normalize_path("/api/requisitos/{identificador}")


def test_governed_paths_cover_runtime_and_requisitos() -> None:
    paths = {path for _, path in GOVERNED_PATHS}
    assert "/api/runtime/health" in paths
    assert "/api/requisitos" in paths
    assert any("requisitos" in path and "{param}" in _normalize_path(path) for _, path in GOVERNED_PATHS)
