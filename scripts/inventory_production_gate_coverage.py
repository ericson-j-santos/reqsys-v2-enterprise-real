#!/usr/bin/env python3
"""Inventory production-capable workflows and their governance gate coverage."""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PRODUCTION_PATTERNS = (
    re.compile(r"environment:\s*production", re.IGNORECASE),
    re.compile(r"flyctl\s+deploy", re.IGNORECASE),
    re.compile(r"--environment\s+prod", re.IGNORECASE),
    re.compile(r"--app\s+reqsys-(?:api|app)\b", re.IGNORECASE),
)
PROTECTION_MARKERS = (
    "REQSYS_PRODUCTION_GOVERNANCE_GATE",
    "generate_bacen_nonprod_tolerance_decision.py",
    "evaluate_environment_promotion_gate.py",
    "environment-promotion-readiness-gate.yml",
)
EXCLUDED_SELF = "production-gate-coverage-inventory.yml"


def inspect_workflow(path: Path, root: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(root.parent.parent).as_posix()
    if path.name == EXCLUDED_SELF:
        return None
    production_signals = sorted(
        pattern.pattern for pattern in PRODUCTION_PATTERNS if pattern.search(text)
    )
    if not production_signals:
        return None
    protection_markers = sorted(marker for marker in PROTECTION_MARKERS if marker in text)
    return {
        "path": relative,
        "production_signals": production_signals,
        "protection_markers": protection_markers,
        "protected": bool(protection_markers),
    }


def build_inventory(workflow_dir: Path) -> dict[str, Any]:
    workflows: list[dict[str, Any]] = []
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(workflow_dir.glob(pattern)):
            inspected = inspect_workflow(path, workflow_dir)
            if inspected:
                workflows.append(inspected)

    protected = [item for item in workflows if item["protected"]]
    unprotected = [item for item in workflows if not item["protected"]]
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-production-gate-coverage-inventory",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory_until_all_paths_are_migrated",
        "summary": {
            "production_capable_workflows": len(workflows),
            "protected_workflows": len(protected),
            "unprotected_workflows": len(unprotected),
        },
        "workflows": workflows,
        "unprotected_workflows": unprotected,
        "delivery_blocker": bool(unprotected),
        "automatic_enforcement_ready": not unprotected,
        "production_touched": False,
        "next_stage": (
            "enable_blocking_enforcement"
            if not unprotected
            else "migrate_each_unprotected_workflow_to_the_governed_production_gate"
        ),
    }


def render_issue_body(inventory: dict[str, Any]) -> str:
    lines = [
        "<!-- reqsys-production-gate-coverage -->",
        "# Caminhos de produção sem gate governado",
        "",
        "Esta issue é mantida automaticamente pelo inventário de workflows de produção.",
        "",
        f"- Workflows capazes de produção: **{inventory['summary']['production_capable_workflows']}**",
        f"- Protegidos: **{inventory['summary']['protected_workflows']}**",
        f"- Não protegidos: **{inventory['summary']['unprotected_workflows']}**",
        "",
        "## Pendências",
        "",
    ]
    for item in inventory["unprotected_workflows"]:
        lines.append(f"- `{item['path']}`")
    lines.extend(
        [
            "",
            "## Critério de encerramento",
            "",
            "Todos os workflows capazes de tocar produção devem consumir o gate BACEN/Environment Promotion antes de acessar secrets, environment `production` ou comandos de deploy.",
            "",
            "`production_touched=false`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue-body", type=Path, required=True)
    args = parser.parse_args()

    inventory = build_inventory(args.workflow_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.issue_body.write_text(render_issue_body(inventory), encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
