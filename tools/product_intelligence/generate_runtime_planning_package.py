#!/usr/bin/env python3
"""Generate Product Intelligence runtime planning package.

This package is review-only. It does not deploy, mutate production, create
external tickets, call external AI providers or execute agents.
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


def build_package(report_dir: Path) -> dict[str, Any]:
    dashboard = read_json(report_dir / "reqsys-product-intelligence-dashboard.json")
    decision = read_json(report_dir / "product-decision-intelligence.json")
    roadmap = read_json(report_dir / "product-intelligence-functional-roadmap.json")
    readiness_gate = read_json(report_dir / "product-intelligence-runtime-readiness-gate.json")

    signals = readiness_gate.get("signals") if isinstance(readiness_gate.get("signals"), dict) else {}
    phases = roadmap.get("phases") if isinstance(roadmap.get("phases"), list) else []
    requirement = dashboard.get("requirement") if isinstance(dashboard.get("requirement"), dict) else {}

    readiness = readiness_gate.get("runtime_readiness", "UNKNOWN")
    gate_status = readiness_gate.get("gate_status", "UNKNOWN")

    plan_status = "blocked"
    if gate_status == "PASS" and readiness == "READY_FOR_GOVERNED_PLANNING":
        plan_status = "ready_for_review"
    elif gate_status == "PASS":
        plan_status = "review_with_warnings"

    workstreams = [
        {
            "id": "ws-functional-scope",
            "name": "Functional scope confirmation",
            "objective": "Confirmar escopo funcional antes de qualquer planejamento de runtime.",
            "required_evidence": ["requisito aprovado", "critérios BDD", "decisão funcional revisada"],
            "owner": "human_reviewer",
        },
        {
            "id": "ws-runtime-constraints",
            "name": "Runtime constraints review",
            "objective": "Revisar restrições de ambiente, segurança, dados e operação.",
            "required_evidence": ["gates de segurança", "rastreabilidade", "limites de execução"],
            "owner": "human_reviewer",
        },
        {
            "id": "ws-test-readiness",
            "name": "Test readiness planning",
            "objective": "Planejar testes funcionais, regressão e evidências antes de implementação.",
            "required_evidence": ["testes vinculados", "score funcional", "grafo de rastreabilidade"],
            "owner": "human_reviewer",
        },
        {
            "id": "ws-release-governance",
            "name": "Release governance planning",
            "objective": "Definir critérios mínimos para release sem mutação automática de produção.",
            "required_evidence": ["aprovação humana", "CI verde", "plano de rollback"],
            "owner": "human_reviewer",
        },
    ]

    return {
        "schema_version": "1.0.0",
        "package": "product-intelligence-runtime-planning-package",
        "mode": "review_only",
        "plan_status": plan_status,
        "requirement": requirement,
        "signals": signals,
        "decision": decision.get("decision", "UNKNOWN"),
        "runtime_readiness": readiness,
        "gate_status": gate_status,
        "roadmap_phases_count": len(phases),
        "workstreams": workstreams,
        "mandatory_controls": [
            "human_review_required",
            "ci_green_required",
            "traceability_required",
            "rollback_plan_required",
            "no_external_write_without_approval",
            "no_agent_execution_without_approval",
        ],
        "governance": {
            "external_write": "disabled",
            "agent_execution": "disabled",
            "production_mutation": "disabled",
            "external_ai_call": "disabled",
            "human_review_required": True,
        },
    }


def write_reports(package: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-runtime-planning-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    ws_rows = "\n".join(
        f"| {ws['id']} | {ws['name']} | {ws['owner']} | {ws['objective']} |"
        for ws in package["workstreams"]
    )
    controls = "\n".join(f"- {control}" for control in package["mandatory_controls"])
    req = package.get("requirement") if isinstance(package.get("requirement"), dict) else {}

    markdown = f"""# Product Intelligence Runtime Planning Package

| Field | Value |
|---|---|
| Requirement | {req.get('id', 'unknown')} |
| Title | {req.get('title', 'unknown')} |
| Plan status | {package['plan_status']} |
| Runtime readiness | {package['runtime_readiness']} |
| Gate status | {package['gate_status']} |
| Decision | {package['decision']} |
| Mode | {package['mode']} |

## Workstreams

| ID | Name | Owner | Objective |
|---|---|---|---|
{ws_rows}

## Mandatory controls

{controls}

## Governance

- External write: disabled
- Agent execution: disabled
- Production mutation: disabled
- External AI call: disabled
- Human review required: true
"""
    (report_dir / "product-intelligence-runtime-planning-package.md").write_text(markdown, encoding="utf-8")

    html_rows = "".join(
        f"<tr><td>{ws['id']}</td><td>{ws['name']}</td><td>{ws['owner']}</td><td>{ws['objective']}</td></tr>"
        for ws in package["workstreams"]
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Runtime Planning Package</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:28px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Runtime Planning Package</h1>
<div class="grid">
<div class="card"><div class="label">Plan Status</div><div class="metric">{package['plan_status']}</div></div>
<div class="card"><div class="label">Runtime Readiness</div><div class="metric">{package['runtime_readiness']}</div></div>
<div class="card"><div class="label">Gate</div><div class="metric">{package['gate_status']}</div></div>
<div class="card"><div class="label">Workstreams</div><div class="metric">{len(package['workstreams'])}</div></div>
</div>
<div class="section"><h2>Workstreams</h2><table><tr><th>ID</th><th>Name</th><th>Owner</th><th>Objective</th></tr>{html_rows}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-runtime-planning-package.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        package = build_package(report_dir)
        write_reports(package, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Runtime planning package generated: {package['plan_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
