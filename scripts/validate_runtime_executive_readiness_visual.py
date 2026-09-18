#!/usr/bin/env python3
"""Valida presença visual do Executive Readiness nos painéis públicos."""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_SNIPPETS = {
    Path("docs/ops-dashboard/index.html"): [
        "executive-readiness-visual-card",
        "Executive Readiness — decisão de produção",
        "exec-readiness-decision",
        "exec-readiness-production-ready",
        "renderExecutiveReadinessVisual(payload)",
        "cards.executive_readiness",
    ],
    Path("docs/ops-dashboard/runtime-executive.html"): [
        "executive-readiness-visual-card",
        "Executive Readiness",
        "readiness-decision",
        "readiness-production",
        "renderExecutiveReadiness(payload)",
        "executive_readiness",
    ],
}


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def main() -> int:
    for path, snippets in REQUIRED_SNIPPETS.items():
        if not path.exists():
            return fail(f"arquivo ausente: {path}")
        html = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in html:
                return fail(f"snippet ausente em {path}: {snippet}")
    print("Executive Readiness visual validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
