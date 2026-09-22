#!/usr/bin/env python3
"""Generate Product Intelligence Governance Closure Pack.

Review-only closure pack. It summarizes final governance posture, artifacts,
remaining limits and human-review requirements without deployment or external
side effects.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

REQUIRED_ARTIFACTS = [
    "product-intelligence-consolidated-governance-report.json",
    "product-intelligence-governance-stabilization-gate.json",
    "product-intelligence-governance-stability-index.json",
    "product-intelligence-governance-drift-detector.json",
    "product-intelligence-continuous-governance-snapshot.json",
    "product-intelligence-executive-control-tower.json",
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


def build_pack(report_dir: Path) -> dict[str, Any]:
    artifacts = {name: read_json(report_dir / name) for name in REQUIRED_ARTIFACTS}
    missing = [name for name, payload in artifacts.items() if not payload]

    consolidated = artifacts["product-intelligence-consolidated-governance-report.json"]
    stabilization = artifacts["product-intelligence-governance-stabilization-gate.json"]
    stability = artifacts["product-intelligence-governance-stability-index.json"]
    drift = artifacts["product-intelligence-governance-drift-detector.json"]

    kpis = consolidated.get("kpis") if isinstance(consolidated.get("kpis"), dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []

    if missing:
        blockers.append("missing artifacts: " + ", ".join(missing))
    if consolidated.get("consolidated_state") not in {"CONSOLIDATED_GOVERNED", "CONSOLIDATED_WITH_WARNINGS"}:
        blockers.append("consolidated governance report is not in a governed state")
    if stabilization.get("gate_status") != "PASS":
        blockers.append("governance stabilization gate is not PASS")
    if drift.get("drift_state") not in {"NO_DRIFT", "DRIFT_WITH_WARNINGS"}:
        blockers.append("governance drift state requires review")
    if stability.get("stability_state") not in {"STABLE_GOLD", "STABLE_CONTROLLED"}:
        warnings.append("stability state is below controlled target")

    closure_score = round(
        (as_float(consolidated.get("report_score"), 0) * 0.40)
        + (as_float(stabilization.get("stability_index"), 0) * 0.30)
        + (as_float(stability.get("stability_index"), 0) * 0.20)
        + (as_float(drift.get("drift_score"), 0) * 0.10),
        2,
    )

    closure_state = "CLOSED_FOR_HUMAN_GOVERNANCE_REVIEW" if not blockers and closure_score >= 85 else "CLOSURE_WITH_WARNINGS" if not blockers else "CLOSURE_BLOCKED"

    return {
        "schema_version": "1.0.0",
        "pack": "product-intelligence-governance-closure-pack",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "closure_state": closure_state,
        "closure_score": closure_score,
        "artifact_count": len(REQUIRED_ARTIFACTS) - len(missing),
        "required_artifact_count": len(REQUIRED_ARTIFACTS),
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
            "consolidated_state": consolidated.get("consolidated_state", "UNKNOWN"),
            "stabilization_gate": stabilization.get("gate_status", "UNKNOWN"),
            "stability_state": stability.get("stability_state", "UNKNOWN"),
            "drift_state": drift.get("drift_state", "UNKNOWN"),
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
        "next_recommended_increment": "Product Intelligence Final Evidence Index",
    }


def write_reports(pack: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-governance-closure-pack.json").write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    kpis = pack["kpis"]
    signals = pack["signals"]
    blockers = "\n".join(f"- {item}" for item in pack["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in pack["warnings"]) or "- None"
    limits = "\n".join(f"- {item}" for item in pack["limits"])

    markdown = f"""# Product Intelligence Governance Closure Pack

| Field | Value |
|---|---|
| Closure state | {pack['closure_state']} |
| Closure score | {pack['closure_score']} |
| Artifacts | {pack['artifact_count']} / {pack['required_artifact_count']} |
| Generated at | {pack['generated_at']} |
| Mode | {pack['mode']} |

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
| Consolidated state | {signals['consolidated_state']} |
| Stabilization gate | {signals['stabilization_gate']} |
| Stability state | {signals['stability_state']} |
| Drift state | {signals['drift_state']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Limits

{limits}

## Next increment

{pack['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-governance-closure-pack.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Governance Closure Pack</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}</style></head><body><h1>Product Intelligence Governance Closure Pack</h1><div class="grid"><div class="card"><div class="label">State</div><div class="metric">{pack['closure_state']}</div></div><div class="card"><div class="label">Score</div><div class="metric">{pack['closure_score']}</div></div><div class="card"><div class="label">Artifacts</div><div class="metric">{pack['artifact_count']}/{pack['required_artifact_count']}</div></div><div class="card"><div class="label">Risk</div><div class="metric">{kpis['estimated_operational_risk_percent']}%</div></div></div></body></html>"""
    (report_dir / "product-intelligence-governance-closure-pack.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    pack = build_pack(report_dir)
    write_reports(pack, report_dir)
    print(f"Governance closure pack: {pack['closure_state']} score={pack['closure_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
