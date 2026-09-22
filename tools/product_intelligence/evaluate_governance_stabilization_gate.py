#!/usr/bin/env python3
"""Evaluate Product Intelligence Governance Stabilization Gate.

Review-only gate. It evaluates whether the Product Intelligence governance layer is
stable enough for human-controlled consolidation. It does not deploy, mutate
production, create issues, call external providers or execute agents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

MIN_STABILITY_INDEX = 85.0
MAX_RISK_PERCENT = 12.0
MIN_CONFIDENCE_PERCENT = 82.0


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


def evaluate(report_dir: Path) -> dict[str, Any]:
    stability = read_json(report_dir / "product-intelligence-governance-stability-index.json")
    drift = read_json(report_dir / "product-intelligence-governance-drift-detector.json")
    snapshot = read_json(report_dir / "product-intelligence-continuous-governance-snapshot.json")

    inputs = stability.get("inputs") if isinstance(stability.get("inputs"), dict) else {}
    kpis = snapshot.get("kpis") if isinstance(snapshot.get("kpis"), dict) else {}

    stability_index = as_float(stability.get("stability_index"), 0)
    risk_percent = as_float(inputs.get("risk_percent") or kpis.get("estimated_operational_risk_percent"), 100)
    confidence_percent = as_float(inputs.get("confidence_percent") or kpis.get("statistical_confidence_percent"), 0)
    drift_count = int(drift.get("drift_count") or 0)
    warning_count = int(drift.get("warning_count") or 0)

    blockers: list[str] = []
    warnings: list[str] = []

    if stability_index < MIN_STABILITY_INDEX:
        blockers.append(f"stability_index below minimum: {stability_index} < {MIN_STABILITY_INDEX}")
    if risk_percent > MAX_RISK_PERCENT:
        blockers.append(f"risk_percent above maximum: {risk_percent} > {MAX_RISK_PERCENT}")
    if confidence_percent < MIN_CONFIDENCE_PERCENT:
        blockers.append(f"confidence_percent below minimum: {confidence_percent} < {MIN_CONFIDENCE_PERCENT}")
    if drift_count > 0:
        blockers.append(f"open governance drifts detected: {drift_count}")
    if warning_count > 0:
        warnings.append(f"governance warnings detected: {warning_count}")

    gate_status = "PASS" if not blockers else "FAIL"
    stabilization_state = "STABILIZED_FOR_HUMAN_CONSOLIDATION" if gate_status == "PASS" and not warnings else "STABILIZED_WITH_WARNINGS" if gate_status == "PASS" else "NOT_STABILIZED"

    return {
        "schema_version": "1.0.0",
        "gate": "product-intelligence-governance-stabilization-gate",
        "mode": "review_only",
        "gate_status": gate_status,
        "stabilization_state": stabilization_state,
        "stability_index": stability_index,
        "risk_percent": risk_percent,
        "confidence_percent": confidence_percent,
        "drift_count": drift_count,
        "warning_count": warning_count,
        "blockers": blockers,
        "warnings": warnings,
        "thresholds": {
            "min_stability_index": MIN_STABILITY_INDEX,
            "max_risk_percent": MAX_RISK_PERCENT,
            "min_confidence_percent": MIN_CONFIDENCE_PERCENT,
            "max_drift_count": 0,
        },
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_call": "disabled",
            "human_review_required": True,
        },
        "next_recommended_increment": "Product Intelligence Consolidated Governance Report",
    }


def write_reports(result: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-governance-stabilization-gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    blockers = "\n".join(f"- {item}" for item in result["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in result["warnings"]) or "- None"
    markdown = f"""# Product Intelligence Governance Stabilization Gate

| Field | Value |
|---|---|
| Gate status | {result['gate_status']} |
| Stabilization state | {result['stabilization_state']} |
| Stability index | {result['stability_index']} |
| Risk percent | {result['risk_percent']}% |
| Confidence percent | {result['confidence_percent']}% |
| Drift count | {result['drift_count']} |
| Warning count | {result['warning_count']} |
| Mode | {result['mode']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Governance

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External call: disabled
- Human review required: true

## Next increment

{result['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-governance-stabilization-gate.md").write_text(markdown, encoding="utf-8")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Governance Stabilization Gate</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}</style></head><body><h1>Product Intelligence Governance Stabilization Gate</h1><div class="grid"><div class="card"><div class="label">Gate</div><div class="metric">{result['gate_status']}</div></div><div class="card"><div class="label">State</div><div class="metric">{result['stabilization_state']}</div></div><div class="card"><div class="label">Stability</div><div class="metric">{result['stability_index']}</div></div><div class="card"><div class="label">Risk</div><div class="metric">{result['risk_percent']}%</div></div></div></body></html>"""
    (report_dir / "product-intelligence-governance-stabilization-gate.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    result = evaluate(report_dir)
    write_reports(result, report_dir)
    print(f"Governance stabilization gate: {result['gate_status']} {result['stabilization_state']}")
    if result["gate_status"] != "PASS":
        for blocker in result["blockers"]:
            print(f"BLOCKER: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
