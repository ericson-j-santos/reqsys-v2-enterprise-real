#!/usr/bin/env python3
"""Valida o manifesto de Versão Mínima Controlada do ReqSys."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED_CONTROLS = (
    "versioning",
    "artifact_manifest",
    "environment_configuration",
    "secret_scanning",
    "input_validation",
    "error_handling",
    "structured_logging",
    "automated_tests",
    "ci",
    "changelog",
    "execution_instructions",
    "rollback",
    "evidence",
)
ALLOWED_MATURITY = {"EXPERIMENTAL", "MINIMUM_CONTROLLED", "OPERATIONAL", "GOLD_STANDARD"}


def validate_manifest(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("reqsys_schema") != "1.0":
        errors.append("reqsys_schema deve ser 1.0")
    version = data.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("version deve seguir Versionamento Semântico")
    maturity = data.get("maturity")
    if maturity not in ALLOWED_MATURITY:
        errors.append("maturity inválido")

    controls = data.get("controls")
    if not isinstance(controls, dict):
        errors.append("controls deve ser objeto")
        controls = {}
    for name in REQUIRED_CONTROLS:
        status = controls.get(name)
        if status not in {"PASS", "FAIL"}:
            errors.append(f"controle obrigatório ausente/inválido: {name}")

    contextual = data.get("contextual_controls")
    if not isinstance(contextual, dict):
        errors.append("contextual_controls deve ser objeto")
        contextual = {}
    for name, value in contextual.items():
        if value in {"PASS", "FAIL"}:
            continue
        if not isinstance(value, dict) or value.get("status") != "NOT_APPLICABLE" or len(str(value.get("justification") or "").strip()) < 3:
            errors.append(f"controle contextual inválido: {name}")

    all_required_pass = all(controls.get(name) == "PASS" for name in REQUIRED_CONTROLS)
    no_contextual_fail = all(value != "FAIL" for value in contextual.values())
    expected_release_allowed = all_required_pass and no_contextual_fail
    release_allowed = data.get("release_allowed")
    if not isinstance(release_allowed, bool):
        errors.append("release_allowed deve ser booleano")
    elif release_allowed != expected_release_allowed:
        errors.append(f"release_allowed inconsistente; esperado {str(expected_release_allowed).lower()}")

    if maturity in {"MINIMUM_CONTROLLED", "OPERATIONAL", "GOLD_STANDARD"} and not expected_release_allowed:
        errors.append(f"maturity={maturity} exige todos os controles mínimos aplicáveis aprovados")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    errors = validate_manifest(data)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
