#!/usr/bin/env python3
"""Generate ReqSys Product Intelligence Living Backlog.

The backlog is derived from governed product intelligence artifacts. It does not
call external systems, does not open issues automatically and does not execute
agents. It produces deterministic JSON, Markdown and HTML artifacts for review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"
DEFAULT_EVENT_PATH = ROOT / "examples" / "product-intelligence" / "product-intelligence-event.example.json"


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


def load_context(report_dir: Path, event_path: Path) -> dict[str, Any]:
    return {
        "event": read_json(event_path),
        "score": read_json(report_dir / "requirement-quality-score.json"),
        "graph": read_json(report_dir / "functional-traceability-graph.json"),
        "dashboard": read_json(report_dir / "reqsys-product-intelligence-dashboard.json"),
        "decision": read_json(report_dir / "product-decision-intelligence.json"),
    }


def classify_priority(final_score: float, traceability: float, decision: str) -> str:
    if decision == "BLOCK_AND_REFINE" or final_score < 40 or traceability < 20:
        return "P0"
    if decision == "REFINE_BEFORE_IMPLEMENTATION" or final_score < 75 or traceability < 60:
        return "P1"
    return "P2"


def build_backlog(context: dict[str, Any]) -> dict[str, Any]:
    event = context.get("event") or {}
    requirement = event.get("requirement") if isinstance(event.get("requirement"), dict) else {}
    governance = event.get("governance") if isinstance(event.get("governance"), dict) else {}
    score = context.get("score") or {}
    graph = context.get("graph") or {}
    dashboard = context.get("dashboard") or {}
    decision_payload = context.get("decision") or {}
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}

    requirement_id = str(requirement.get("id") or "unknown")
    final_score = float(score.get("final_score") or 0)
    traceability = float(graph_summary.get("traceability_coverage_score") or 0)
    decision = str(decision_payload.get("decision") or "REFINE_BEFORE_IMPLEMENTATION")
    priority = classify_priority(final_score, traceability, decision)

    items: list[dict[str, Any]] = []

    items.append({
        "id": f"{requirement_id}-quality-refinement",
        "type": "quality_refinement",
        "priority": priority,
        "title": "Refinar qualidade funcional do requisito",
        "reason": score.get("recommendation", "Review requirement quality."),
        "acceptance_criteria": [
            "Score funcional recalculado.",
            "Critérios BDD revisados.",
            "Ambiguidade e risco reavaliados."
        ],
        "status": "candidate",
        "human_review_required": True,
    })

    items.append({
        "id": f"{requirement_id}-traceability-completion",
        "type": "traceability_completion",
        "priority": "P1" if traceability < 60 else "P2",
        "title": "Completar rastreabilidade funcional",
        "reason": graph_summary.get("recommendation", "Review traceability links."),
        "acceptance_criteria": [
            "Vínculos com PRs, testes, decisões e riscos avaliados.",
            "Grafo funcional regenerado.",
            "Cobertura de rastreabilidade revisada."
        ],
        "status": "candidate",
        "human_review_required": True,
    })

    items.append({
        "id": f"{requirement_id}-decision-review",
        "type": "decision_review",
        "priority": priority,
        "title": "Revisar decisão funcional assistida",
        "reason": decision,
        "acceptance_criteria": [
            "Racional da decisão revisado por humano.",
            "Próximas ações confirmadas ou ajustadas.",
            "Evidências funcionais anexadas quando aplicável."
        ],
        "status": "candidate",
        "human_review_required": True,
    })

    return {
        "schema_version": "1.0.0",
        "backlog": "reqsys-product-intelligence-living-backlog",
        "requirement_id": requirement_id,
        "product_readiness": dashboard.get("product_readiness", "UNKNOWN"),
        "signals": {
            "quality_score": final_score,
            "traceability_coverage": traceability,
            "decision": decision,
            "risk_band": score.get("risk_band", "UNKNOWN"),
        },
        "governance": {
            "correlation_id": governance.get("correlation_id"),
            "pii_masked": governance.get("pii_masked"),
            "human_review_required": True,
            "external_write": "disabled",
            "agent_execution": "disabled",
        },
        "items": items,
    }


def write_reports(backlog: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "reqsys-product-intelligence-living-backlog.json").write_text(
        json.dumps(backlog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rows = "\n".join(
        f"| {item['id']} | {item['type']} | {item['priority']} | {item['status']} | {item['title']} |"
        for item in backlog["items"]
    )
    markdown = f"""# ReqSys Product Intelligence Living Backlog

| Field | Value |
|---|---|
| Requirement | {backlog['requirement_id']} |
| Product readiness | {backlog['product_readiness']} |
| Quality score | {backlog['signals']['quality_score']} |
| Traceability coverage | {backlog['signals']['traceability_coverage']}% |
| Decision | {backlog['signals']['decision']} |

## Backlog items

| ID | Type | Priority | Status | Title |
|---|---|---|---|---|
{rows}

## Governance

| Field | Value |
|---|---|
| Correlation ID | {backlog['governance']['correlation_id']} |
| PII masked | {backlog['governance']['pii_masked']} |
| Human review required | {backlog['governance']['human_review_required']} |
| External write | {backlog['governance']['external_write']} |
| Agent execution | {backlog['governance']['agent_execution']} |
"""
    (report_dir / "reqsys-product-intelligence-living-backlog.md").write_text(markdown, encoding="utf-8")

    html_rows = "".join(
        f"<tr><td>{item['id']}</td><td>{item['type']}</td><td>{item['priority']}</td><td>{item['status']}</td><td>{item['title']}</td></tr>"
        for item in backlog["items"]
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReqSys Product Intelligence Living Backlog</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
.title{{font-size:32px;font-weight:bold}}
.badge{{padding:10px 18px;border-radius:999px;background:#1e3a8a;color:#bfdbfe;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:32px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<div class="header"><div class="title">ReqSys Product Intelligence Living Backlog</div><div class="badge">{backlog['product_readiness']}</div></div>
<div class="grid">
<div class="card"><div class="label">Quality Score</div><div class="metric">{backlog['signals']['quality_score']}</div></div>
<div class="card"><div class="label">Traceability</div><div class="metric">{backlog['signals']['traceability_coverage']}%</div></div>
<div class="card"><div class="label">Decision</div><div class="metric">{backlog['signals']['decision']}</div></div>
<div class="card"><div class="label">Items</div><div class="metric">{len(backlog['items'])}</div></div>
</div>
<div class="section"><h2>Backlog Items</h2><table><tr><th>ID</th><th>Type</th><th>Priority</th><th>Status</th><th>Title</th></tr>{html_rows}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "reqsys-product-intelligence-living-backlog.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    report_dir = Path(argv[2]) if len(argv) > 2 else REPORT_DIR
    try:
        context = load_context(report_dir, event_path)
        backlog = build_backlog(context)
        write_reports(backlog, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Living backlog generated: {len(backlog['items'])} candidate items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
