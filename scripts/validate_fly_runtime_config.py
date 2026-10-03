#!/usr/bin/env python3
"""Valida, sem rede, que o runtime Fly.io permanece aposentado."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "flyio-retirement-policy.json"


def _load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _prefix(path: Path, lines: int = 80) -> str:
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[:lines])


def validate() -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    if not POLICY_PATH.is_file():
        payload = {"ok": False, "errors": [f"politica ausente: {POLICY_PATH}"]}
        return 1, payload

    policy = _load_policy()
    marker = str(policy.get("guard_marker") or "")
    if policy.get("status") != "PERMANENTLY_RETIRED":
        errors.append("status deve ser PERMANENTLY_RETIRED")
    if policy.get("mutations_allowed") is not False:
        errors.append("mutations_allowed deve ser false")
    if policy.get("reactivation_allowed") is not False:
        errors.append("reactivation_allowed deve ser false")
    if not marker:
        errors.append("guard_marker obrigatorio")

    forbidden_manifests = list(policy.get("forbidden_manifests", []))
    for relative_path in forbidden_manifests:
        if (ROOT / relative_path).exists():
            errors.append(f"manifesto Fly proibido foi reintroduzido: {relative_path}")

    discovered_manifests = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("fly*.toml")
        if not {".git", ".venv", "node_modules"}.intersection(path.parts)
    )
    if discovered_manifests:
        errors.append(
            "manifestos Fly inesperados: " + ", ".join(discovered_manifests)
        )

    guarded_entrypoints = list(policy.get("mutating_entrypoints", []))
    for relative_path in guarded_entrypoints:
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"entrypoint aposentado ausente: {relative_path}")
        elif marker not in _prefix(path):
            errors.append(f"entrypoint sem guard de aposentadoria: {relative_path}")

    legacy_artifacts = list(policy.get("legacy_build_artifacts", []))
    for relative_path in legacy_artifacts:
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"artefato legado ausente sem atualizar politica: {relative_path}")
        elif marker not in _prefix(path):
            errors.append(f"artefato legado ainda executavel sem guard: {relative_path}")

    payload = {
        "ok": not errors,
        "schema_version": "2.0.0",
        "mode": "permanent_retirement",
        "status": policy.get("status"),
        "validated_files": [
            POLICY_PATH.relative_to(ROOT).as_posix(),
            *guarded_entrypoints,
            *legacy_artifacts,
        ],
        "forbidden_manifests": forbidden_manifests,
        "errors": errors,
    }
    return (0 if not errors else 1), payload


def main() -> int:
    exit_code, payload = validate()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
