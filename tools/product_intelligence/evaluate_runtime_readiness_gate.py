#!/usr/bin/env python3
"""Evaluate Product Intelligence runtime readiness.

This gate checks whether a requirement intelligence package is ready for governed
runtime planning. It does not deploy, mutate production, create issues or execute
agents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def evaluate(report_dir: Path) -> dict[str, Any]:
    dashboard = read_json(report_dir / "reqsys-product-intelligence-dashboard.json")
    decision = read_json(report_dir / "product-decision-intelligence.json")
    roadmap = read_json(report_dir / "product-intelligence-functional-roadmap.json")
    backlog_gate = read_json(report_dir / "product-intelligence-backlog-governance-gate.json")

    readiness = str(dashboard.get("product_readiness") or "UNKNOWN")
    decision_value = str(decision.get("decision") or "UNKNOWN")
    backlog_gate_status = str(backlog_gate.get("gate_status") or "UNKNOWN")
    roadmap_mode = str(roadmap.get("mode") or "UNKNOWN")
    phases = roadmap.get("phases") if isinstance(roadmap.get("phases"), list) else []

    blockers: list[str] = []
    warnings: list[str] = []

    if backlog_gate_status != "PASS":
        blockers.append("backlog governance gate must pass before runtime readiness")
    if roadmap_mode != "review_only":
        blockers.append("roadmap must remain review_only")
    if decision.get("human_review_required") is not True:
        blockers.append("human review must be required before runtime planning")
    if decision.get("governance", {}).get("agent_execution") != "disabled":
        blockers.append("agent execution must remain disabled")
    if decision.get("governance", {}).get("external_ai_call") != "disabled":
        blockers.append("external AI calls must remain disabled")

    if readiness != "READY_FOR_IMPLEMENTATION":
        warnings.append(f"product_readiness is {readiness}; implementation planning should remain conservative")
    if decision_value != "PROCEED_TO_GOVERNED_IMPLEMENTATION":
        warnings.append(f"decision is {decision_value}; runtime planning may require refinement first")
    if not phases:
        blockers.append("functional roadmap phases are required")

    gate_status = "PASS" if not blockers else "FAIL"
    runtime_readiness = "READY_FOR_GOVERNED_PLANNING" if gate_status == "PASS" and not warnings else "READY_WITH_WARNINGS" if gate_status == "PASS" else "NOT_READY"
    risk_level = "LOW" if runtime_readiness == "READY_FOR_GOVERNED_PLANNING" else "MEDIUM" if gate_status == "PASS" else "HIGH"

    return {
        "schema_version": "1.0.0",
        "gate": "product-intelligence-runtime-readiness-gate",
        "gate_status": gate_status,
        "runtime_readiness": runtime_readiness,
        "risk_level": risk_level,
        "signals": {
            "product_readiness": readiness,
            "decision": decision_value,
            "backlog_governance_gate": backlog_gate_status,
            "roadmap_mode": roadmap_mode,
            "phases_count": len(phases),
        },
        "blockers": blockers,
        "warnings": warnings,
        "governance": {
            "external_write": "disabled",
            "agent_execution": "disabled",
            "production_mutation": "disabled",
            "human_review_required": True,
        },
    }


def write_reports(result: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-runtime-readiness-gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    blockers = "\n".join(f"- {item}" for item in result["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in result["warnings"]) or "- None"
    signals = result["signals"]

    markdown = f"""# Product Intelligence Runtime Readiness Gate

| Field | Value |
|---|---|
| Gate status | {result['gate_status']} |
| Runtime readiness | {result['runtime_readiness']} |
| Risk level | {result['risk_level']} |
| Product readiness | {signals['product_readiness']} |
| Decision | {signals['decision']} |
| Backlog governance gate | {signals['backlog_governance_gate']} |
| Roadmap mode | {signals['roadmap_mode']} |
| Phases | {signals['phases_count']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Governance

- External write: disabled
- Agent execution: disabled
- Production mutation: disabled
- Human review required: true
"""
    (report_dir / "product-intelligence-runtime-readiness-gate.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Runtime Readiness Gate</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:28px;font-weight:bold;margin-top:8px;color:#22c55e}}
.section{{margin-top:28px}}
pre{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px;white-space:pre-wrap}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Runtime Readiness Gate</h1>
<div class="grid">
<div class="card"><div class="label">Gate</div><div class="metric">{result['gate_status']}</div></div>
<div class="card"><div class="label">Runtime Readiness</div><div class="metric">{result['runtime_readiness']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{result['risk_level']}</div></div>
<div class="card"><div class="label">Decision</div><div class="metric">{signals['decision']}</div></div>
</div>
<div class="section"><h2>Blockers</h2><pre>{blockers}</pre></div>
<div class="section"><h2>Warnings</h2><pre>{warnings}</pre></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-runtime-readiness-gate.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        result = evaluate(report_dir)
        write_reports(result, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Runtime readiness gate: {result['gate_status']} ({result['runtime_readiness']})")
    if result["gate_status"] != "PASS":
        for blocker in result["blockers"]:
            print(f"BLOCKER: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
