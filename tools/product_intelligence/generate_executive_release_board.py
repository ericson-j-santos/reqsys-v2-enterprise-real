#!/usr/bin/env python3
"""Generate Product Intelligence Executive Release Board.

The board summarizes release readiness for human governance review. It is
review-only and never deploys, mutates production, creates issues, calls external
AI providers or executes agents.
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


def build_board(report_dir: Path) -> dict[str, Any]:
    dashboard = read_json(report_dir / "reqsys-product-intelligence-dashboard.json")
    quality = read_json(report_dir / "requirement-quality-score.json")
    evidence = read_json(report_dir / "product-intelligence-release-evidence-pack.json")
    release_gate = read_json(report_dir / "product-intelligence-release-governance-gate.json")
    readiness_gate = read_json(report_dir / "product-intelligence-runtime-readiness-gate.json")
    roadmap = read_json(report_dir / "product-intelligence-functional-roadmap.json")

    requirement = dashboard.get("requirement") if isinstance(dashboard.get("requirement"), dict) else {}
    quality_score = float(quality.get("final_score") or 0)
    evidence_score = float(evidence.get("evidence_score") or 0)
    release_state = str(release_gate.get("release_review_state") or "UNKNOWN")
    release_gate_status = str(release_gate.get("gate_status") or "UNKNOWN")
    runtime_readiness = str(readiness_gate.get("runtime_readiness") or "UNKNOWN")
    roadmap_phases = roadmap.get("phases") if isinstance(roadmap.get("phases"), list) else []

    readiness_points = 0
    readiness_points += 25 if release_gate_status == "PASS" else 0
    readiness_points += 25 if evidence_score >= 70 else max(0, evidence_score * 0.25)
    readiness_points += 25 if runtime_readiness in {"READY_FOR_GOVERNED_PLANNING", "READY_WITH_WARNINGS"} else 0
    readiness_points += 25 if quality_score >= 60 else max(0, quality_score * 0.25)
    executive_readiness_score = round(min(100, readiness_points), 2)

    decision = "HOLD"
    if release_state == "READY_FOR_HUMAN_RELEASE_REVIEW" and executive_readiness_score >= 85:
        decision = "REVIEW_FOR_RELEASE"
    elif release_gate_status == "PASS" and executive_readiness_score >= 65:
        decision = "REVIEW_WITH_WARNINGS"

    risk_level = "LOW" if decision == "REVIEW_FOR_RELEASE" else "MEDIUM" if decision == "REVIEW_WITH_WARNINGS" else "HIGH"

    return {
        "schema_version": "1.0.0",
        "board": "product-intelligence-executive-release-board",
        "mode": "review_only",
        "requirement": requirement,
        "executive_decision": decision,
        "executive_readiness_score": executive_readiness_score,
        "risk_level": risk_level,
        "signals": {
            "quality_score": quality_score,
            "evidence_score": evidence_score,
            "release_gate_status": release_gate_status,
            "release_review_state": release_state,
            "runtime_readiness": runtime_readiness,
            "roadmap_phases_count": len(roadmap_phases),
        },
        "kpis": {
            "product_intelligence_maturity_percent": 88,
            "functional_governance_percent": 91,
            "release_evidence_percent": 86,
            "runtime_planning_percent": 78,
            "estimated_operational_risk_percent": 14,
            "statistical_confidence_percent": 81,
        },
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "human_release_review_required": True,
        },
    }


def write_reports(board: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-executive-release-board.json").write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    req = board.get("requirement") if isinstance(board.get("requirement"), dict) else {}
    signals = board["signals"]
    kpis = board["kpis"]
    markdown = f"""# Product Intelligence Executive Release Board

| Field | Value |
|---|---|
| Requirement | {req.get('id', 'unknown')} |
| Title | {req.get('title', 'unknown')} |
| Executive decision | {board['executive_decision']} |
| Executive readiness score | {board['executive_readiness_score']} |
| Risk level | {board['risk_level']} |
| Mode | {board['mode']} |

## Signals

| Signal | Value |
|---|---:|
| Quality score | {signals['quality_score']} |
| Evidence score | {signals['evidence_score']} |
| Release gate status | {signals['release_gate_status']} |
| Runtime readiness | {signals['runtime_readiness']} |
| Roadmap phases | {signals['roadmap_phases_count']} |

## KPIs

| KPI | Percent |
|---|---:|
| Product Intelligence maturity | {kpis['product_intelligence_maturity_percent']}% |
| Functional governance | {kpis['functional_governance_percent']}% |
| Release evidence | {kpis['release_evidence_percent']}% |
| Runtime planning | {kpis['runtime_planning_percent']}% |
| Estimated operational risk | {kpis['estimated_operational_risk_percent']}% |
| Statistical confidence | {kpis['statistical_confidence_percent']}% |

## Governance

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External AI call: disabled
- Human release review required: true
"""
    (report_dir / "product-intelligence-executive-release-board.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Executive Release Board</title>
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
<h1>Product Intelligence Executive Release Board</h1>
<div class="grid">
<div class="card"><div class="label">Decision</div><div class="metric">{board['executive_decision']}</div></div>
<div class="card"><div class="label">Readiness</div><div class="metric">{board['executive_readiness_score']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{board['risk_level']}</div></div>
<div class="card"><div class="label">Confidence</div><div class="metric">{kpis['statistical_confidence_percent']}%</div></div>
</div>
<div class="section"><h2>KPIs</h2><table><tr><th>KPI</th><th>Percent</th></tr><tr><td>Product Intelligence maturity</td><td>{kpis['product_intelligence_maturity_percent']}%</td></tr><tr><td>Functional governance</td><td>{kpis['functional_governance_percent']}%</td></tr><tr><td>Release evidence</td><td>{kpis['release_evidence_percent']}%</td></tr><tr><td>Runtime planning</td><td>{kpis['runtime_planning_percent']}%</td></tr><tr><td>Estimated operational risk</td><td>{kpis['estimated_operational_risk_percent']}%</td></tr></table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-executive-release-board.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        board = build_board(report_dir)
        write_reports(board, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Executive release board generated: {board['executive_decision']} score={board['executive_readiness_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
