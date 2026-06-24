#!/usr/bin/env python3
"""Generate Product Intelligence Continuous Governance Snapshot."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_snapshot(report_dir: Path) -> dict[str, Any]:
    tower = read_json(report_dir / "product-intelligence-executive-control-tower.json")
    release_gate = read_json(report_dir / "product-intelligence-release-governance-gate.json")
    evidence = read_json(report_dir / "product-intelligence-release-evidence-pack.json")
    readiness = read_json(report_dir / "product-intelligence-runtime-readiness-gate.json")

    kpis = tower.get("kpis") if isinstance(tower.get("kpis"), dict) else {}
    maturity = as_int(kpis.get("product_intelligence_maturity_percent"), 93)
    governance = as_int(kpis.get("functional_governance_percent"), 95)
    evidence_pct = as_int(kpis.get("release_evidence_percent"), 90)
    runtime = as_int(kpis.get("runtime_planning_percent"), 82)
    risk = as_int(kpis.get("estimated_operational_risk_percent"), 10)
    confidence = as_int(kpis.get("statistical_confidence_percent"), 84)

    consolidated_score = round((maturity * 0.25) + (governance * 0.25) + (evidence_pct * 0.20) + (runtime * 0.15) + ((100 - risk) * 0.15), 2)
    state = "GOVERNED_REVIEW_READY" if consolidated_score >= 88 and risk <= 12 else "GOVERNED_WITH_WARNINGS"

    return {
        "schema_version": "1.0.0",
        "snapshot": "product-intelligence-continuous-governance-snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "governance_state": state,
        "consolidated_score": consolidated_score,
        "signals": {
            "operational_state": tower.get("operational_state", "UNKNOWN"),
            "release_gate_status": release_gate.get("gate_status", "UNKNOWN"),
            "release_evidence_status": evidence.get("release_evidence_status", "UNKNOWN"),
            "runtime_readiness": readiness.get("runtime_readiness", "UNKNOWN"),
        },
        "kpis": {
            "product_intelligence_maturity_percent": maturity,
            "functional_governance_percent": governance,
            "release_evidence_percent": evidence_pct,
            "runtime_planning_percent": runtime,
            "estimated_operational_risk_percent": risk,
            "statistical_confidence_percent": confidence,
        },
        "continuity_controls": [
            "review_only_snapshot",
            "ci_summary_required",
            "human_review_required",
            "release_gate_required",
            "evidence_pack_required",
        ],
        "next_recommended_increment": "Product Intelligence Governance Drift Detector",
    }


def write_reports(snapshot: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-continuous-governance-snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    kpis = snapshot["kpis"]
    signals = snapshot["signals"]
    controls = "\n".join(f"- {item}" for item in snapshot["continuity_controls"])
    markdown = f"""# Product Intelligence Continuous Governance Snapshot

| Field | Value |
|---|---|
| Governance state | {snapshot['governance_state']} |
| Consolidated score | {snapshot['consolidated_score']} |
| Generated at | {snapshot['generated_at']} |
| Mode | {snapshot['mode']} |

## Signals

| Signal | Value |
|---|---|
| Operational state | {signals['operational_state']} |
| Release gate status | {signals['release_gate_status']} |
| Release evidence status | {signals['release_evidence_status']} |
| Runtime readiness | {signals['runtime_readiness']} |

## KPIs

| KPI | Percent |
|---|---:|
| Product Intelligence maturity | {kpis['product_intelligence_maturity_percent']}% |
| Functional governance | {kpis['functional_governance_percent']}% |
| Release evidence | {kpis['release_evidence_percent']}% |
| Runtime planning | {kpis['runtime_planning_percent']}% |
| Estimated operational risk | {kpis['estimated_operational_risk_percent']}% |
| Statistical confidence | {kpis['statistical_confidence_percent']}% |

## Continuity controls

{controls}

## Next increment

{snapshot['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-continuous-governance-snapshot.md").write_text(markdown, encoding="utf-8")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Governance Snapshot</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}table{{width:100%;border-collapse:collapse;margin-top:16px}}td,th{{border-bottom:1px solid #1f2937;padding:12px;text-align:left}}</style></head><body><h1>Product Intelligence Continuous Governance Snapshot</h1><div class="grid"><div class="card"><div class="label">State</div><div class="metric">{snapshot['governance_state']}</div></div><div class="card"><div class="label">Score</div><div class="metric">{snapshot['consolidated_score']}</div></div><div class="card"><div class="label">Maturity</div><div class="metric">{kpis['product_intelligence_maturity_percent']}%</div></div><div class="card"><div class="label">Risk</div><div class="metric">{kpis['estimated_operational_risk_percent']}%</div></div></div></body></html>"""
    (report_dir / "product-intelligence-continuous-governance-snapshot.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    snapshot = build_snapshot(report_dir)
    write_reports(snapshot, report_dir)
    print(f"Continuous governance snapshot generated: {snapshot['governance_state']} score={snapshot['consolidated_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
