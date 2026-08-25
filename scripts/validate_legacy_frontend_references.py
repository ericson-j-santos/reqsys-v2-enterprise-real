#!/usr/bin/env python3
"""Falha quando frontends legados reaparecem em superfícies operacionais do ReqSys."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MARKERS = ("frontend-angular", "frontend-vuetify")
STATIC_SURFACES = (
    "playwright.config.ts",
    "package.json",
    "scripts/validar_qualidade.sh",
)


def operational_surfaces(repo_root: Path = REPO_ROOT) -> list[Path]:
    surfaces = [repo_root / path for path in STATIC_SURFACES]
    workflow_dir = repo_root / ".github" / "workflows"
    if workflow_dir.exists():
        surfaces.extend(sorted(workflow_dir.glob("*.yml")))
        surfaces.extend(sorted(workflow_dir.glob("*.yaml")))
    return surfaces


def find_legacy_references(repo_root: Path = REPO_ROOT) -> list[str]:
    findings: list[str] = []
    for path in operational_surfaces(repo_root):
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(repo_root).as_posix()
        for marker in LEGACY_MARKERS:
            if marker in content:
                findings.append(f"{relative}: referência operacional a {marker}")
    return findings


def main() -> int:
    findings = find_legacy_references()
    if findings:
        print("Referências operacionais a frontends legados detectadas:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print("Zero referências operacionais a frontend-angular/frontend-vuetify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
