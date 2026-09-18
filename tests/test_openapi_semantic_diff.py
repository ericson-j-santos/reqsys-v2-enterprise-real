from __future__ import annotations

import json
from pathlib import Path

from scripts.openapi_semantic_diff import (
    _normalize_path,
    build_semantic_diff,
    extract_backend_routes,
    extract_openapi_routes,
)


def test_normalize_path_collapses_params() -> None:
    assert _normalize_path("/api/requisitos/{id}") == "/api/requisitos/{param}"
    assert _normalize_path("/api/requisitos/{identificador}") == "/api/requisitos/{param}"


def test_extract_openapi_routes_from_current_contract() -> None:
    contract = json.loads(
        Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json").read_text(encoding="utf-8")
    )
    routes = extract_openapi_routes(contract)

    assert ("GET", "/api/runtime/health") in routes
    assert ("GET", "/api/requisitos/{param}") in routes
    assert ("POST", "/api/requisitos") in routes


def test_extract_backend_routes_includes_runtime_contract_paths() -> None:
    routes = extract_backend_routes(Path("backend/app/api"))

    assert ("GET", "/api/runtime/health") in routes
    assert ("GET", "/api/runtime/dashboard") in routes
    assert ("GET", "/api/runtime/analytics") in routes
    assert ("GET", "/api/requisitos/{param}") in routes
    assert ("POST", "/api/requisitos") in routes


def test_semantic_diff_runtime_contract_detects_current_backend_drifts() -> None:
    report = build_semantic_diff(
        Path("docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json"),
        Path("backend/app/api"),
        scope="runtime_contract",
    )

    assert report["status"] in {"passed", "drift_detected"}
    assert report["summary"]["backend_routes"] > 0
    assert report["summary"]["openapi_routes"] > 0

    missing_in_openapi = [
        item for item in report["drifts"] if item["code"] == "missing_in_openapi"
    ]

    assert report["summary"]["missing_in_openapi"] == len(missing_in_openapi)
    assert report["summary"]["missing_in_backend"] == 0
    assert all(item["backend_path"].startswith("/api/runtime") for item in missing_in_openapi)


def test_semantic_diff_report_only_exits_zero_on_drift(tmp_path: Path) -> None:
    import subprocess
    import sys

    output = tmp_path / "diff.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/openapi_semantic_diff.py",
            "--output",
            str(output),
            "--scope",
            "runtime_contract",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert completed.returncode == 0
    assert payload["summary"]["drift_count"] >= 0
