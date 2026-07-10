#!/usr/bin/env python3
"""Valida o card visual Workflow Efficiency no Ops Dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_TOKENS = {
    'id="workflow-efficiency-visual-card"',
    'id="workflow-efficiency-score"',
    'id="workflow-efficiency-trend"',
    'id="workflow-efficiency-savings"',
    'id="workflow-efficiency-action"',
    'function renderWorkflowEfficiency(payload)',
    'renderWorkflowEfficiency(payload);',
    'payload?.cards?.workflow_efficiency',
    'payload?.links?.workflow_efficiency',
    'runtime-executive-index.json',
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida card visual Workflow Efficiency")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    args = parser.parse_args()

    if not args.dashboard.exists():
        raise SystemExit(f"dashboard ausente: {args.dashboard}")

    html = args.dashboard.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_TOKENS if token not in html)
    if missing:
        raise SystemExit(f"tokens ausentes: {missing}")

    if html.count('id="workflow-efficiency-visual-card"') != 1:
        raise SystemExit("card visual deve existir exatamente uma vez")
    if html.count("function renderWorkflowEfficiency(payload)") != 1:
        raise SystemExit("função de renderização deve existir exatamente uma vez")
    if "fetch('http" in html or "fetch(\"http" in html:
        raise SystemExit("card não pode introduzir chamadas externas")

    print(json.dumps({"status": "passed", "card": "workflow_efficiency", "source": "runtime-executive-index.json"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
