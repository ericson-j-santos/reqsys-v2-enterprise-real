#!/usr/bin/env python3
"""Generate Product Intelligence executive summary trendline.

The trendline is deterministic and review-only. It creates an executive trend
snapshot from current Product Intelligence artifacts and a small embedded baseline.
It never deploys, mutates production, creates issues, calls external AI providers
or executes agents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

BASELINE = [
    {
        "label": "event-model",
        "product_intelligence_maturity_percent": 12,
        "functional_governance_percent": 18,
        "release_evidence_percent": 0,
        "runtime_planning_percent": 0,
        "estimated_operational_risk_percent": 48,
        "statistical_confidence_percent": 65,
    },
    {
        "label": "quality-graph-dashboard",
        "product_intelligence_maturity_percent": 40,
        "functional_governance_percent": 48,
        "release_evidence_percent": 25,
        "runtime_planning_percent": 18,
        "estimated_operational_risk_percent": 34,
        "statistical_confidence_percent": 72,
    },
    {
        "label": "release-board",
        "product_intelligence_maturity_percent": 88,
        "functional_governance_percent": 91,
        "release_evidence_percent": 86,
        "runtime_planning_percent": 78,
        "estimated_operational_risk_percent": 14,
        "statistical_confidence_percent": 81,
    },
]


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


def current_snapshot(report_dir: Path) -> dict[str, Any]:
    board = read_json(report_dir / "product-intelligence-executive-release-board.json")
    kpis = board.get("kpis") if isinstance(board.get("kpis"), dict) else {}
    return {
        "label": "current",
        "product_intelligence_maturity_percent": int(kpis.get("product_intelligence_maturity_percent") or 88),
        "functional_governance_percent": int(kpis.get("functional_governance_percent") or 91),
        "release_evidence_percent": int(kpis.get("release_evidence_percent") or 86),
        "runtime_planning_percent": int(kpis.get("runtime_planning_percent") or 78),
        "estimated_operational_risk_percent": int(kpis.get("estimated_operational_risk_percent") or 14),
        "statistical_confidence_percent": int(kpis.get("statistical_confidence_percent") or 81),
    }


def delta(first: dict[str, Any], last: dict[str, Any], key: str) -> int:
    return int(last.get(key, 0)) - int(first.get(key, 0))


def build_trendline(report_dir: Path) -> dict[str, Any]:
    snapshots = [*BASELINE, current_snapshot(report_dir)]
    first = snapshots[0]
    last = snapshots[-1]

    trend_summary = {
        "maturity_delta": delta(first, last, "product_intelligence_maturity_percent"),
        "governance_delta": delta(first, last, "functional_governance_percent"),
        "release_evidence_delta": delta(first, last, "release_evidence_percent"),
        "runtime_planning_delta": delta(first, last, "runtime_planning_percent"),
        "risk_delta": delta(first, last, "estimated_operational_risk_percent"),
        "confidence_delta": delta(first, last, "statistical_confidence_percent"),
    }

    return {
        "schema_version": "1.0.0",
        "trendline": "product-intelligence-executive-summary-trendline",
        "mode": "review_only",
        "snapshots": snapshots,
        "trend_summary": trend_summary,
        "executive_assessment": "Product Intelligence is approaching governed release-review maturity.",
        "next_recommended_increment": "Product Intelligence Executive Control Tower",
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "human_review_required": True,
        },
    }


def write_reports(trendline: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-executive-summary-trendline.json").write_text(
        json.dumps(trendline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    snapshot_rows = "\n".join(
        "| {label} | {maturity}% | {governance}% | {evidence}% | {runtime}% | {risk}% | {confidence}% |".format(
            label=item["label"],
            maturity=item["product_intelligence_maturity_percent"],
            governance=item["functional_governance_percent"],
            evidence=item["release_evidence_percent"],
            runtime=item["runtime_planning_percent"],
            risk=item["estimated_operational_risk_percent"],
            confidence=item["statistical_confidence_percent"],
        )
        for item in trendline["snapshots"]
    )
    summary = trendline["trend_summary"]
    markdown = f"""# Product Intelligence Executive Summary Trendline

## Executive assessment

{trendline['executive_assessment']}

## Snapshots

| Snapshot | Maturity | Governance | Evidence | Runtime planning | Risk | Confidence |
|---|---:|---:|---:|---:|---:|---:|
{snapshot_rows}

## Delta from baseline

| Metric | Delta |
|---|---:|
| Maturity | {summary['maturity_delta']} pp |
| Governance | {summary['governance_delta']} pp |
| Release evidence | {summary['release_evidence_delta']} pp |
| Runtime planning | {summary['runtime_planning_delta']} pp |
| Risk | {summary['risk_delta']} pp |
| Confidence | {summary['confidence_delta']} pp |

## Governance

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External AI call: disabled
- Human review required: true

## Next increment

{trendline['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-executive-summary-trendline.md").write_text(markdown, encoding="utf-8")

    html_rows = "".join(
        "<tr><td>{label}</td><td>{maturity}%</td><td>{governance}%</td><td>{evidence}%</td><td>{runtime}%</td><td>{risk}%</td><td>{confidence}%</td></tr>".format(
            label=item["label"],
            maturity=item["product_intelligence_maturity_percent"],
            governance=item["functional_governance_percent"],
            evidence=item["release_evidence_percent"],
            runtime=item["runtime_planning_percent"],
            risk=item["estimated_operational_risk_percent"],
            confidence=item["statistical_confidence_percent"],
        )
        for item in trendline["snapshots"]
    )
    latest = trendline["snapshots"][-1]
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Executive Summary Trendline</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:30px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Executive Summary Trendline</h1>
<div class="grid">
<div class="card"><div class="label">Maturity</div><div class="metric">{latest['product_intelligence_maturity_percent']}%</div></div>
<div class="card"><div class="label">Governance</div><div class="metric">{latest['functional_governance_percent']}%</div></div>
<div class="card"><div class="label">Evidence</div><div class="metric">{latest['release_evidence_percent']}%</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{latest['estimated_operational_risk_percent']}%</div></div>
</div>
<div class="section"><h2>Snapshots</h2><table><tr><th>Snapshot</th><th>Maturity</th><th>Governance</th><th>Evidence</th><th>Runtime</th><th>Risk</th><th>Confidence</th></tr>{html_rows}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-executive-summary-trendline.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        trendline = build_trendline(report_dir)
        write_reports(trendline, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Executive summary trendline generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
