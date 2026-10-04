#!/usr/bin/env python3
"""Generate a governed functional roadmap from Product Intelligence artifacts.

The roadmap is deterministic and review-only. It does not create issues, does
not write to external tools and does not execute agents.
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


def load_context(report_dir: Path) -> dict[str, Any]:
    return {
        "dashboard": read_json(report_dir / "reqsys-product-intelligence-dashboard.json"),
        "decision": read_json(report_dir / "product-decision-intelligence.json"),
        "backlog": read_json(report_dir / "reqsys-product-intelligence-living-backlog.json"),
        "gate": read_json(report_dir / "product-intelligence-backlog-governance-gate.json"),
    }


def build_roadmap(context: dict[str, Any]) -> dict[str, Any]:
    dashboard = context.get("dashboard") or {}
    decision = context.get("decision") or {}
    backlog = context.get("backlog") or {}
    gate = context.get("gate") or {}

    signals = backlog.get("signals") if isinstance(backlog.get("signals"), dict) else {}
    items = backlog.get("items") if isinstance(backlog.get("items"), list) else []
    requirement_id = str(backlog.get("requirement_id") or "unknown")
    readiness = str(dashboard.get("product_readiness") or backlog.get("product_readiness") or "UNKNOWN")
    gate_status = str(gate.get("gate_status") or "UNKNOWN")
    decision_value = str(decision.get("decision") or signals.get("decision") or "UNKNOWN")

    phases: list[dict[str, Any]] = []

    phases.append({
        "id": "phase-1-refinement",
        "name": "Refinamento funcional governado",
        "objective": "Elevar qualidade, BDD, clareza e prontidão do requisito.",
        "entry_criteria": ["Evento funcional válido", "Score funcional disponível"],
        "exit_criteria": ["Ambiguidade revisada", "BDD revisado", "Score recalculado"],
        "priority": "P1",
        "status": "candidate",
    })

    phases.append({
        "id": "phase-2-traceability",
        "name": "Rastreabilidade funcional viva",
        "objective": "Conectar requisito a PRs, testes, decisões e riscos.",
        "entry_criteria": ["Grafo funcional gerado"],
        "exit_criteria": ["Links funcionais revisados", "Cobertura de rastreabilidade reavaliada"],
        "priority": "P1",
        "status": "candidate",
    })

    phases.append({
        "id": "phase-3-governed-implementation",
        "name": "Implementação governada",
        "objective": "Preparar implementação com revisão humana e evidências funcionais.",
        "entry_criteria": ["Gate governado aprovado", "Decisão funcional revisada"],
        "exit_criteria": ["Plano de implementação aprovado", "Testes vinculados", "Evidências anexadas"],
        "priority": "P2" if gate_status == "PASS" else "P1",
        "status": "blocked" if gate_status != "PASS" else "candidate",
    })

    phases.append({
        "id": "phase-4-product-intelligence-feedback",
        "name": "Feedback e aprendizado funcional",
        "objective": "Reexecutar analytics funcionais após refinamento/implementação.",
        "entry_criteria": ["Mudança funcional concluída"],
        "exit_criteria": ["Dashboard recalculado", "Backlog vivo atualizado", "Decisão reavaliada"],
        "priority": "P2",
        "status": "candidate",
    })

    return {
        "schema_version": "1.0.0",
        "roadmap": "product-intelligence-functional-roadmap",
        "mode": "review_only",
        "requirement_id": requirement_id,
        "product_readiness": readiness,
        "decision": decision_value,
        "gate_status": gate_status,
        "signals": signals,
        "backlog_items_count": len(items),
        "phases": phases,
        "governance": {
            "external_write": "disabled",
            "agent_execution": "disabled",
            "manual_review_required": True,
        },
    }


def write_reports(roadmap: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-functional-roadmap.json").write_text(
        json.dumps(roadmap, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rows = "\n".join(
        f"| {phase['id']} | {phase['name']} | {phase['priority']} | {phase['status']} | {phase['objective']} |"
        for phase in roadmap["phases"]
    )
    markdown = f"""# Product Intelligence Functional Roadmap

| Field | Value |
|---|---|
| Requirement | {roadmap['requirement_id']} |
| Product readiness | {roadmap['product_readiness']} |
| Decision | {roadmap['decision']} |
| Gate status | {roadmap['gate_status']} |
| Backlog items | {roadmap['backlog_items_count']} |
| Mode | {roadmap['mode']} |

## Roadmap phases

| ID | Phase | Priority | Status | Objective |
|---|---|---|---|---|
{rows}

## Governance

- External write: disabled
- Agent execution: disabled
- Manual review required: true
"""
    (report_dir / "product-intelligence-functional-roadmap.md").write_text(markdown, encoding="utf-8")

    html_rows = "".join(
        f"<tr><td>{phase['id']}</td><td>{phase['name']}</td><td>{phase['priority']}</td><td>{phase['status']}</td><td>{phase['objective']}</td></tr>"
        for phase in roadmap["phases"]
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Functional Roadmap</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
.title{{font-size:32px;font-weight:bold}}
.badge{{padding:10px 18px;border-radius:999px;background:#1e3a8a;color:#bfdbfe;font-weight:bold}}
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
<div class="header"><div class="title">Product Intelligence Functional Roadmap</div><div class="badge">{roadmap['mode']}</div></div>
<div class="grid">
<div class="card"><div class="label">Readiness</div><div class="metric">{roadmap['product_readiness']}</div></div>
<div class="card"><div class="label">Decision</div><div class="metric">{roadmap['decision']}</div></div>
<div class="card"><div class="label">Gate</div><div class="metric">{roadmap['gate_status']}</div></div>
<div class="card"><div class="label">Phases</div><div class="metric">{len(roadmap['phases'])}</div></div>
</div>
<div class="section"><h2>Roadmap phases</h2><table><tr><th>ID</th><th>Phase</th><th>Priority</th><th>Status</th><th>Objective</th></tr>{html_rows}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-functional-roadmap.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        context = load_context(report_dir)
        roadmap = build_roadmap(context)
        write_reports(roadmap, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Functional roadmap generated: {len(roadmap['phases'])} phases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
