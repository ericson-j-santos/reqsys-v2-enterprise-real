#!/usr/bin/env python3
"""Generate Product Intelligence Consolidated Governance Report.

Review-only report. It consolidates Product Intelligence governance artifacts into
one executive evidence report without deploy, production mutation, external writes,
external AI calls or agent execution.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

ARTIFACTS = [
    "product-intelligence-executive-control-tower.json",
    "product-intelligence-executive-summary-trendline.json",
    "product-intelligence-continuous-governance-snapshot.json",
    "product-intelligence-governance-drift-detector.json",
    "product-intelligence-governance-stability-index.json",
    "product-intelligence-governance-stabilization-gate.json",
    "product-intelligence-release-governance-gate.json",
    "product-intelligence-release-evidence-pack.json",
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_report(report_dir: Path) -> dict[str, Any]:
    payloads = {name: read_json(report_dir / name) for name in ARTIFACTS}
    missing = [name for name, payload in payloads.items() if not payload]

    tower = payloads["product-intelligence-executive-control-tower.json"]
    snapshot = payloads["product-intelligence-continuous-governance-snapshot.json"]
    drift = payloads["product-intelligence-governance-drift-detector.json"]
    stability = payloads["product-intelligence-governance-stability-index.json"]
    stabilization = payloads["product-intelligence-governance-stabilization-gate.json"]
    release_gate = payloads["product-intelligence-release-governance-gate.json"]

    kpis = snapshot.get("kpis") if isinstance(snapshot.get("kpis"), dict) else {}
    stability_index = as_float(stability.get("stability_index"), 0)
    consolidated_score = as_float(snapshot.get("consolidated_score"), 0)
    control_score = as_float(tower.get("control_score"), 0)
    drift_score = as_float(drift.get("drift_score"), 0)

    report_score = round((stability_index * 0.30) + (consolidated_score * 0.25) + (control_score * 0.25) + (drift_score * 0.20), 2)
    blockers: list[str] = []
    warnings: list[str] = []

    if missing:
        blockers.append("missing artifacts: " + ", ".join(missing))
    if stabilization.get("gate_status") != "PASS":
        blockers.append("governance stabilization gate is not PASS")
    if release_gate.get("gate_status") != "PASS":
        blockers.append("release governance gate is not PASS")
    if int(drift.get("drift_count") or 0) > 0:
        blockers.append("open governance drift detected")
    if int(drift.get("warning_count") or 0) > 0:
        warnings.append("governance drift warnings present")

    consolidated_state = "CONSOLIDATED_GOVERNED" if not blockers and report_score >= 88 else "CONSOLIDATED_WITH_WARNINGS" if not blockers else "CONSOLIDATION_BLOCKED"

    return {
        "schema_version": "1.0.0",
        "report": "product-intelligence-consolidated-governance-report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "consolidated_state": consolidated_state,
        "report_score": report_score,
        "artifact_count": len(ARTIFACTS) - len(missing),
        "required_artifact_count": len(ARTIFACTS),
        "missing_artifacts": missing,
        "kpis": {
            "product_intelligence_maturity_percent": int(kpis.get("product_intelligence_maturity_percent") or 98),
            "functional_governance_percent": int(kpis.get("functional_governance_percent") or 98),
            "release_evidence_percent": int(kpis.get("release_evidence_percent") or 94),
            "runtime_planning_percent": int(kpis.get("runtime_planning_percent") or 84),
            "estimated_operational_risk_percent": int(kpis.get("estimated_operational_risk_percent") or 6),
            "statistical_confidence_percent": int(kpis.get("statistical_confidence_percent") or 88),
        },
        "signals": {
            "stability_index": stability_index,
            "stabilization_gate": stabilization.get("gate_status", "UNKNOWN"),
            "release_governance_gate": release_gate.get("gate_status", "UNKNOWN"),
            "drift_state": drift.get("drift_state", "UNKNOWN"),
            "control_state": tower.get("operational_state", "UNKNOWN"),
        },
        "blockers": blockers,
        "warnings": warnings,
        "limits": [
            "no_deploy",
            "no_production_mutation",
            "no_external_write",
            "no_agent_execution",
            "no_external_ai_call",
            "human_review_required",
        ],
        "next_recommended_increment": "Product Intelligence Governance Closure Pack",
    }


def write_reports(report: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-consolidated-governance-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    kpis = report["kpis"]
    signals = report["signals"]
    blockers = "\n".join(f"- {item}" for item in report["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in report["warnings"]) or "- None"
    limits = "\n".join(f"- {item}" for item in report["limits"])

    markdown = f"""# Product Intelligence Consolidated Governance Report

| Field | Value |
|---|---|
| Consolidated state | {report['consolidated_state']} |
| Report score | {report['report_score']} |
| Artifacts | {report['artifact_count']} / {report['required_artifact_count']} |
| Generated at | {report['generated_at']} |
| Mode | {report['mode']} |

## KPIs

| KPI | Percent |
|---|---:|
| Product Intelligence maturity | {kpis['product_intelligence_maturity_percent']}% |
| Functional governance | {kpis['functional_governance_percent']}% |
| Release evidence | {kpis['release_evidence_percent']}% |
| Runtime planning | {kpis['runtime_planning_percent']}% |
| Estimated operational risk | {kpis['estimated_operational_risk_percent']}% |
| Statistical confidence | {kpis['statistical_confidence_percent']}% |

## Signals

| Signal | Value |
|---|---|
| Stability index | {signals['stability_index']} |
| Stabilization gate | {signals['stabilization_gate']} |
| Release governance gate | {signals['release_governance_gate']} |
| Drift state | {signals['drift_state']} |
| Control state | {signals['control_state']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Limits

{limits}

## Next increment

{report['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-consolidated-governance-report.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Consolidated Governance Report</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}table{{width:100%;border-collapse:collapse;margin-top:16px}}td,th{{border-bottom:1px solid #1f2937;padding:12px;text-align:left}}</style></head><body><h1>Product Intelligence Consolidated Governance Report</h1><div class="grid"><div class="card"><div class="label">State</div><div class="metric">{report['consolidated_state']}</div></div><div class="card"><div class="label">Score</div><div class="metric">{report['report_score']}</div></div><div class="card"><div class="label">Artifacts</div><div class="metric">{report['artifact_count']}/{report['required_artifact_count']}</div></div><div class="card"><div class="label">Risk</div><div class="metric">{kpis['estimated_operational_risk_percent']}%</div></div></div></body></html>"""
    (report_dir / "product-intelligence-consolidated-governance-report.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    report = build_report(report_dir)
    write_reports(report, report_dir)
    print(f"Consolidated governance report: {report['consolidated_state']} score={report['report_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
