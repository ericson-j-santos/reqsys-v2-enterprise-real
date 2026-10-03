from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.openapi_breaking_change_gate import find_breaking_changes


def _contract() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "test", "version": "1.0.0"},
        "paths": {
            "/api/items": {
                "get": {
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "requestBody": {"required": False, "content": {"application/json": {}}},
                    "responses": {"201": {"description": "created"}},
                },
            }
        },
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "integer"},
                        "state": {"type": "string", "enum": ["new", "done"]},
                    },
                }
            }
        },
    }


def test_additive_optional_change_is_compatible() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["components"]["schemas"]["Item"]["properties"]["note"] = {"type": "string"}

    assert find_breaking_changes(base, candidate) == []


def test_removed_operation_is_breaking() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    del candidate["paths"]["/api/items"]["post"]

    changes = find_breaking_changes(base, candidate)

    assert any(item["code"] == "operation_removed" for item in changes)


def test_parameter_becoming_required_is_breaking() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["paths"]["/api/items"]["get"]["parameters"][0]["required"] = True

    changes = find_breaking_changes(base, candidate)

    assert any(item["code"] == "required_parameter_added" for item in changes)


def test_required_schema_property_added_is_breaking() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["components"]["schemas"]["Item"]["properties"]["name"] = {"type": "string"}
    candidate["components"]["schemas"]["Item"]["required"].append("name")

    changes = find_breaking_changes(base, candidate)

    assert any(item["code"] == "required_schema_property_added" for item in changes)


def test_enum_narrowing_is_breaking() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["components"]["schemas"]["Item"]["properties"]["state"]["enum"] = ["new"]

    changes = find_breaking_changes(base, candidate)

    assert any(item["code"] == "enum_narrowed" for item in changes)


def test_strict_cli_negative_control_blocks_known_breaking_change(tmp_path: Path) -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    del candidate["paths"]["/api/items"]["post"]

    base_path = tmp_path / "base.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "report.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/openapi_breaking_change_gate.py",
            "--base",
            str(base_path),
            "--candidate",
            str(candidate_path),
            "--output",
            str(output_path),
            "--strict",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert report["status"] == "breaking_change_detected"
    assert report["summary"]["breaking_change_count"] >= 1


def test_strict_cli_accepts_additive_change(tmp_path: Path) -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["components"]["schemas"]["Item"]["properties"]["note"] = {"type": "string"}

    base_path = tmp_path / "base.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "report.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/openapi_breaking_change_gate.py",
            "--base",
            str(base_path),
            "--candidate",
            str(candidate_path),
            "--output",
            str(output_path),
            "--strict",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert report["status"] == "passed"
    assert report["summary"]["breaking_change_count"] == 0
