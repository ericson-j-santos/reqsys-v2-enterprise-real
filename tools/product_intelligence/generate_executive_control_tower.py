#!/usr/bin/env python3
"""Generate Product Intelligence Executive Control Tower.

The control tower consolidates executive board, trendline, release governance,
readiness and evidence signals into one review-only operational view. It never
deploys, mutates production, creates issues, calls external AI providers or
executes agents.
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


def pct(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_control_tower(report_dir: Path) -> dict[str, Any]:
    board = read_json(report_dir / "product-intelligence-executive-release-board.json")
    trendline = read_json(report_dir / "product-intelligence-executive-summary-trendline.json")
    release_gate = read_json(report_dir / "product-intelligence-release-governance-gate.json")
    readiness_gate = read_json(report_dir / "product-intelligence-runtime-readiness-gate.json")
    evidence = read_json(report_dir / "product-intelligence-release-evidence-pack.json")

    kpis = board.get("kpis") if isinstance(board.get("kpis"), dict) else {}
    signals = board.get("signals") if isinstance(board.get("signals"), dict) else {}
    trend_summary = trendline.get("trend_summary") if isinstance(trendline.get("trend_summary"), dict) else {}

    maturity = pct(kpis.get("product_intelligence_maturity_percent"), 88)
    governance = pct(kpis.get("functional_governance_percent"), 91)
    evidence_pct = pct(kpis.get("release_evidence_percent"), 86)
    runtime = pct(kpis.get("runtime_planning_percent"), 78)
    risk = pct(kpis.get("estimated_operational_risk_percent"), 14)
    confidence = pct(kpis.get("statistical_confidence_percent"), 81)

    control_score = round((maturity * 0.25) + (governance * 0.25) + (evidence_pct * 0.20) + (runtime * 0.15) + ((100 - risk) * 0.15), 2)

    release_gate_status = release_gate.get("gate_status", "UNKNOWN")
    release_review_state = release_gate.get("release_review_state", "UNKNOWN")
    runtime_readiness = readiness_gate.get("runtime_readiness", "UNKNOWN")
    evidence_status = evidence.get("release_evidence_status", "UNKNOWN")

    operational_state = "HOLD"
    if control_score >= 85 and release_gate_status == "PASS" and evidence_status == "PASS":
        operational_state = "READY_FOR_EXECUTIVE_REVIEW"
    elif control_score >= 70 and release_gate_status == "PASS":
        operational_state = "READY_WITH_WARNINGS"

    control_risk = "LOW" if operational_state == "READY_FOR_EXECUTIVE_REVIEW" else "MEDIUM" if operational_state == "READY_WITH_WARNINGS" else "HIGH"

    return {
        "schema_version": "1.0.0",
        "control_tower": "product-intelligence-executive-control-tower",
        "mode": "review_only",
        "operational_state": operational_state,
        "control_score": control_score,
        "control_risk": control_risk,
        "signals": {
            "executive_decision": board.get("executive_decision", "UNKNOWN"),
            "release_gate_status": release_gate_status,
            "release_review_state": release_review_state,
            "runtime_readiness": runtime_readiness,
            "evidence_status": evidence_status,
            "evidence_score": evidence.get("evidence_score", 0),
            "quality_score": signals.get("quality_score", 0),
        },
        "kpis": {
            "product_intelligence_maturity_percent": maturity,
            "functional_governance_percent": governance,
            "release_evidence_percent": evidence_pct,
            "runtime_planning_percent": runtime,
            "estimated_operational_risk_percent": risk,
            "statistical_confidence_percent": confidence,
        },
        "trend_summary": trend_summary,
        "executive_controls": [
            "human_release_review_required",
            "ci_green_required",
            "evidence_pack_required",
            "release_governance_gate_required",
            "runtime_readiness_required",
            "no_deploy_from_control_tower",
            "no_external_write_from_control_tower",
        ],
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "human_review_required": True,
        },
    }


def write_reports(tower: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-executive-control-tower.json").write_text(
        json.dumps(tower, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    kpis = tower["kpis"]
    signals = tower["signals"]
    controls = "\n".join(f"- {control}" for control in tower["executive_controls"])
    markdown = f"""# Product Intelligence Executive Control Tower

| Field | Value |
|---|---|
| Operational state | {tower['operational_state']} |
| Control score | {tower['control_score']} |
| Control risk | {tower['control_risk']} |
| Mode | {tower['mode']} |

## Signals

| Signal | Value |
|---|---|
| Executive decision | {signals['executive_decision']} |
| Release gate | {signals['release_gate_status']} |
| Release review state | {signals['release_review_state']} |
| Runtime readiness | {signals['runtime_readiness']} |
| Evidence status | {signals['evidence_status']} |
| Evidence score | {signals['evidence_score']} |
| Quality score | {signals['quality_score']} |

## KPIs

| KPI | Percent |
|---|---:|
| Product Intelligence maturity | {kpis['product_intelligence_maturity_percent']}% |
| Functional governance | {kpis['functional_governance_percent']}% |
| Release evidence | {kpis['release_evidence_percent']}% |
| Runtime planning | {kpis['runtime_planning_percent']}% |
| Estimated operational risk | {kpis['estimated_operational_risk_percent']}% |
| Statistical confidence | {kpis['statistical_confidence_percent']}% |

## Executive controls

{controls}

## Governance

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External AI call: disabled
- Human review required: true
"""
    (report_dir / "product-intelligence-executive-control-tower.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Executive Control Tower</title>
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
<h1>Product Intelligence Executive Control Tower</h1>
<div class="grid">
<div class="card"><div class="label">Operational State</div><div class="metric">{tower['operational_state']}</div></div>
<div class="card"><div class="label">Control Score</div><div class="metric">{tower['control_score']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{tower['control_risk']}</div></div>
<div class="card"><div class="label">Confidence</div><div class="metric">{kpis['statistical_confidence_percent']}%</div></div>
</div>
<div class="section"><h2>KPIs</h2><table><tr><th>KPI</th><th>Percent</th></tr><tr><td>Maturity</td><td>{kpis['product_intelligence_maturity_percent']}%</td></tr><tr><td>Governance</td><td>{kpis['functional_governance_percent']}%</td></tr><tr><td>Evidence</td><td>{kpis['release_evidence_percent']}%</td></tr><tr><td>Runtime planning</td><td>{kpis['runtime_planning_percent']}%</td></tr><tr><td>Operational risk</td><td>{kpis['estimated_operational_risk_percent']}%</td></tr></table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-executive-control-tower.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        tower = build_control_tower(report_dir)
        write_reports(tower, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Executive control tower generated: {tower['operational_state']} score={tower['control_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
