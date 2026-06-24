#!/usr/bin/env python3
"""Generate governed product decision intelligence for ReqSys.

This script does not call external AI providers and does not execute agents. It
uses deterministic rules over existing Product Intelligence artifacts to produce
a decision recommendation, rationale, risk notes and next actions.
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
    }


def decision_from_context(context: dict[str, Any]) -> dict[str, Any]:
    event = context.get("event") or {}
    requirement = event.get("requirement") if isinstance(event.get("requirement"), dict) else {}
    governance = event.get("governance") if isinstance(event.get("governance"), dict) else {}
    score = context.get("score") or {}
    graph = context.get("graph") or {}
    dashboard = context.get("dashboard") or {}
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}

    final_score = float(score.get("final_score") or 0)
    traceability_coverage = float(graph_summary.get("traceability_coverage_score") or 0)
    risk_band = str(score.get("risk_band") or "UNKNOWN")
    readiness = str(dashboard.get("product_readiness") or "UNKNOWN")

    decision = "REFINE_BEFORE_IMPLEMENTATION"
    confidence = "medium"
    human_review_required = True
    rationale: list[str] = []
    next_actions: list[str] = []

    if final_score >= 75 and traceability_coverage >= 60 and risk_band in {"LOW", "MEDIUM"}:
        decision = "PROCEED_TO_GOVERNED_IMPLEMENTATION"
        confidence = "high"
        rationale.append("Quality score and traceability are sufficient for governed implementation planning.")
        next_actions.extend([
            "Create implementation plan with linked tests.",
            "Bind PR, tests and decision records to the requirement.",
            "Keep human review before production exposure.",
        ])
    elif final_score < 40 or traceability_coverage < 20:
        decision = "BLOCK_AND_REFINE"
        confidence = "high"
        rationale.append("Quality or traceability is below the minimum safe threshold.")
        next_actions.extend([
            "Clarify requirement and acceptance criteria.",
            "Generate or review BDD criteria.",
            "Add traceability links to tests, decisions, risks and PRs.",
        ])
    else:
        rationale.append("Requirement has partial quality/readiness and needs refinement before implementation.")
        next_actions.extend([
            "Improve the lowest scoring quality component.",
            "Add missing traceability links.",
            "Run scoring and dashboard generation again after refinement.",
        ])

    if governance.get("ai_generated") is True:
        human_review_required = True
        rationale.append("AI-generated content requires human review before use as implementation evidence.")

    return {
        "schema_version": "1.0.0",
        "decision_engine": "ai-assisted-product-decision-intelligence",
        "mode": "deterministic_governed_assistive",
        "requirement": {
            "id": requirement.get("id", "unknown"),
            "title": requirement.get("title", "unknown"),
            "type": requirement.get("type", "unknown"),
            "priority": requirement.get("priority", "unknown"),
            "status": requirement.get("status", "unknown"),
        },
        "signals": {
            "quality_score": final_score,
            "traceability_coverage": traceability_coverage,
            "risk_band": risk_band,
            "product_readiness": readiness,
        },
        "decision": decision,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "rationale": rationale,
        "next_actions": next_actions,
        "governance": {
            "correlation_id": governance.get("correlation_id"),
            "pii_masked": governance.get("pii_masked"),
            "evidence_level": governance.get("evidence_level"),
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
        },
    }


def write_reports(decision: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-decision-intelligence.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    req = decision["requirement"]
    signals = decision["signals"]
    governance = decision["governance"]
    rationale = "\n".join(f"- {item}" for item in decision["rationale"])
    next_actions = "\n".join(f"- {item}" for item in decision["next_actions"])

    markdown = f"""# AI-assisted Product Decision Intelligence

| Field | Value |
|---|---|
| Requirement | {req['id']} |
| Title | {req['title']} |
| Decision | {decision['decision']} |
| Confidence | {decision['confidence']} |
| Human review required | {decision['human_review_required']} |
| Mode | {decision['mode']} |

## Signals

| Signal | Value |
|---|---:|
| Quality score | {signals['quality_score']} |
| Traceability coverage | {signals['traceability_coverage']} |
| Risk band | {signals['risk_band']} |
| Product readiness | {signals['product_readiness']} |

## Rationale

{rationale}

## Next actions

{next_actions}

## Governance

| Field | Value |
|---|---|
| Correlation ID | {governance['correlation_id']} |
| PII masked | {governance['pii_masked']} |
| Evidence level | {governance['evidence_level']} |
| Agent execution | {governance['agent_execution']} |
| External AI call | {governance['external_ai_call']} |
"""
    (report_dir / "product-decision-intelligence.md").write_text(markdown, encoding="utf-8")

    html_rationale = "".join(f"<li>{item}</li>" for item in decision["rationale"])
    html_actions = "".join(f"<li>{item}</li>" for item in decision["next_actions"])
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-assisted Product Decision Intelligence</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
.title{{font-size:32px;font-weight:bold}}
.badge{{padding:10px 18px;border-radius:999px;background:#7c2d12;color:#fed7aa;font-weight:bold}}
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
<div class="header"><div class="title">AI-assisted Product Decision Intelligence</div><div class="badge">{decision['decision']}</div></div>
<div class="grid">
<div class="card"><div class="label">Quality Score</div><div class="metric">{signals['quality_score']}</div></div>
<div class="card"><div class="label">Traceability</div><div class="metric">{signals['traceability_coverage']}%</div></div>
<div class="card"><div class="label">Confidence</div><div class="metric">{decision['confidence']}</div></div>
<div class="card"><div class="label">Human Review</div><div class="metric">{decision['human_review_required']}</div></div>
</div>
<div class="section"><h2>Requirement</h2><table><tr><th>ID</th><td>{req['id']}</td></tr><tr><th>Title</th><td>{req['title']}</td></tr><tr><th>Priority</th><td>{req['priority']}</td></tr><tr><th>Status</th><td>{req['status']}</td></tr></table></div>
<div class="section"><h2>Rationale</h2><ul>{html_rationale}</ul></div>
<div class="section"><h2>Next Actions</h2><ul>{html_actions}</ul></div>
</div>
</body>
</html>
"""
    (report_dir / "product-decision-intelligence.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    report_dir = Path(argv[2]) if len(argv) > 2 else REPORT_DIR
    try:
        context = load_context(report_dir, event_path)
        decision = decision_from_context(context)
        write_reports(decision, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Product decision generated: {decision['decision']} ({decision['confidence']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
