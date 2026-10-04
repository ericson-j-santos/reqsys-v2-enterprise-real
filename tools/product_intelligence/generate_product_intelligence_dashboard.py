#!/usr/bin/env python3
"""Generate ReqSys Product Intelligence dashboard artifacts.

This generator consolidates the product event, quality score and traceability
graph into JSON, Markdown and HTML reports for CI artifacts and future UI work.
It uses only Python standard library features.
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


def load_inputs(report_dir: Path, event_path: Path) -> dict[str, Any]:
    event = read_json(event_path)
    score = read_json(report_dir / "requirement-quality-score.json")
    graph = read_json(report_dir / "functional-traceability-graph.json")
    return {"event": event, "score": score, "graph": graph}


def dashboard_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    event = inputs.get("event") or {}
    requirement = event.get("requirement") if isinstance(event.get("requirement"), dict) else {}
    governance = event.get("governance") if isinstance(event.get("governance"), dict) else {}
    score = inputs.get("score") or {}
    graph = inputs.get("graph") or {}
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}

    final_score = float(score.get("final_score") or 0)
    traceability_coverage = float(graph_summary.get("traceability_coverage_score") or 0)
    readiness = "READY_FOR_REFINEMENT"
    if final_score >= 75 and traceability_coverage >= 60:
        readiness = "READY_FOR_IMPLEMENTATION"
    elif final_score < 40 or traceability_coverage < 20:
        readiness = "NEEDS_REFINEMENT"

    return {
        "dashboard": "reqsys-product-intelligence-dashboard",
        "schema_version": "1.0.0",
        "requirement": {
            "id": requirement.get("id", "unknown"),
            "title": requirement.get("title", "unknown"),
            "type": requirement.get("type", "unknown"),
            "status": requirement.get("status", "unknown"),
            "priority": requirement.get("priority", "unknown"),
            "confidence": requirement.get("confidence", "unknown"),
        },
        "quality": {
            "final_score": final_score,
            "maturity_level": score.get("maturity_level", "UNKNOWN"),
            "risk_band": score.get("risk_band", "UNKNOWN"),
            "recommendation": score.get("recommendation", "Review requirement quality."),
        },
        "traceability": {
            "node_count": graph_summary.get("node_count", 0),
            "edge_count": graph_summary.get("edge_count", 0),
            "coverage_score": traceability_coverage,
            "recommendation": graph_summary.get("recommendation", "Review traceability."),
        },
        "governance": {
            "correlation_id": governance.get("correlation_id"),
            "pii_masked": governance.get("pii_masked"),
            "human_review_required": governance.get("human_review_required"),
            "evidence_level": governance.get("evidence_level"),
        },
        "product_readiness": readiness,
    }


def write_reports(payload: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "reqsys-product-intelligence-dashboard.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    req = payload["requirement"]
    quality = payload["quality"]
    trace = payload["traceability"]
    governance = payload["governance"]

    markdown = f"""# ReqSys Product Intelligence Dashboard

| Field | Value |
|---|---|
| Requirement | {req['id']} |
| Title | {req['title']} |
| Type | {req['type']} |
| Status | {req['status']} |
| Priority | {req['priority']} |
| Product readiness | {payload['product_readiness']} |

## Quality

| Metric | Value |
|---|---:|
| Final score | {quality['final_score']} |
| Maturity level | {quality['maturity_level']} |
| Risk band | {quality['risk_band']} |

## Traceability

| Metric | Value |
|---|---:|
| Nodes | {trace['node_count']} |
| Edges | {trace['edge_count']} |
| Coverage | {trace['coverage_score']}% |

## Governance

| Field | Value |
|---|---|
| Correlation ID | {governance['correlation_id']} |
| PII masked | {governance['pii_masked']} |
| Human review required | {governance['human_review_required']} |
| Evidence level | {governance['evidence_level']} |

## Recommendations

- Quality: {quality['recommendation']}
- Traceability: {trace['recommendation']}
"""
    (report_dir / "reqsys-product-intelligence-dashboard.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReqSys Product Intelligence Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
.title{{font-size:32px;font-weight:bold}}
.badge{{padding:10px 18px;border-radius:999px;background:#1e3a8a;color:#bfdbfe;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:34px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<div class="header"><div class="title">ReqSys Product Intelligence Dashboard</div><div class="badge">{payload['product_readiness']}</div></div>
<div class="grid">
<div class="card"><div class="label">Quality Score</div><div class="metric">{quality['final_score']}</div></div>
<div class="card"><div class="label">Maturity</div><div class="metric">{quality['maturity_level']}</div></div>
<div class="card"><div class="label">Risk Band</div><div class="metric">{quality['risk_band']}</div></div>
<div class="card"><div class="label">Traceability Coverage</div><div class="metric">{trace['coverage_score']}%</div></div>
</div>
<div class="section"><h2>Requirement</h2><table><tr><th>ID</th><td>{req['id']}</td></tr><tr><th>Title</th><td>{req['title']}</td></tr><tr><th>Type</th><td>{req['type']}</td></tr><tr><th>Status</th><td>{req['status']}</td></tr><tr><th>Priority</th><td>{req['priority']}</td></tr></table></div>
<div class="section"><h2>Traceability</h2><table><tr><th>Nodes</th><td>{trace['node_count']}</td></tr><tr><th>Edges</th><td>{trace['edge_count']}</td></tr><tr><th>Coverage</th><td>{trace['coverage_score']}%</td></tr></table></div>
<div class="section"><h2>Recommendations</h2><p><b>Quality:</b> {quality['recommendation']}</p><p><b>Traceability:</b> {trace['recommendation']}</p></div>
</div>
</body>
</html>
"""
    (report_dir / "reqsys-product-intelligence-dashboard.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    report_dir = Path(argv[2]) if len(argv) > 2 else REPORT_DIR
    try:
        inputs = load_inputs(report_dir, event_path)
        payload = dashboard_payload(inputs)
        write_reports(payload, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"ReqSys Product Intelligence Dashboard generated: {payload['product_readiness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
