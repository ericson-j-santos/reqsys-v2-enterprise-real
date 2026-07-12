#!/usr/bin/env python3
"""Validate path-based routing for advisory/report-only workflows."""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_ROUTING = {
    ".github/workflows/runtime-risk-scoring.yml": [
        "paths:",
        '      - "backend/**"',
        '      - "frontend/**"',
        '      - "scripts/**"',
        '      - ".github/workflows/**"',
        '      - "docs/ops-dashboard/**"',
        "workflow_dispatch:",
    ],
    ".github/workflows/pr-quality-review.yml": [
        "paths:",
        '      - "backend/**"',
        '      - "frontend/**"',
        '      - "scripts/**"',
        '      - "tests/**"',
        '      - ".github/workflows/**"',
        "workflow_dispatch:",
    ],
    ".github/workflows/predictive-regression-guard.yml": [
        "paths:",
        '      - "backend/**"',
        '      - "frontend/**"',
        '      - "scripts/**"',
        '      - "docs/ops-dashboard/**"',
        "continue-on-error: true",
    ],
}

FORBIDDEN_REQUIRED_GATE_TOKENS = {
    ".github/workflows/reqsys-required-fast-gate.yml": ["paths:", "paths-ignore:"],
}


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def main() -> int:
    for path_text, tokens in REQUIRED_ROUTING.items():
        path = Path(path_text)
        if not path.exists():
            return fail(f"workflow ausente: {path_text}")
        content = path.read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in content]
        if missing:
            return fail(f"{path_text}: tokens de roteamento ausentes: {missing}")

    for path_text, tokens in FORBIDDEN_REQUIRED_GATE_TOKENS.items():
        path = Path(path_text)
        if not path.exists():
            return fail(f"workflow obrigatório ausente: {path_text}")
        content = path.read_text(encoding="utf-8")
        present = [token for token in tokens if token in content]
        if present:
            return fail(f"{path_text}: gate obrigatório não deve ter filtro por path: {present}")

    print("Path-based workflow router validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
