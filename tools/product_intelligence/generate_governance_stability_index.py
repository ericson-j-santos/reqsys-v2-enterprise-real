#!/usr/bin/env python3
"""Generate Product Intelligence Governance Stability Index.

Review-only index. It consolidates governance snapshot, drift detector and control
tower signals into a stability score and operational classification.
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
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_index(report_dir: Path) -> dict[str, Any]:
    snapshot = read_json(report_dir / "product-intelligence-continuous-governance-snapshot.json")
    drift = read_json(report_dir / "product-intelligence-governance-drift-detector.json")
    tower = read_json(report_dir / "product-intelligence-executive-control-tower.json")

    kpis = snapshot.get("kpis") if isinstance(snapshot.get("kpis"), dict) else {}
    consolidated_score = as_float(snapshot.get("consolidated_score"), 0)
    drift_score = as_float(drift.get("drift_score"), 0)
    control_score = as_float(tower.get("control_score"), 0)
    risk = as_float(kpis.get("estimated_operational_risk_percent"), 100)
    confidence = as_float(kpis.get("statistical_confidence_percent"), 0)

    stability_index = round(
        (consolidated_score * 0.30)
        + (drift_score * 0.25)
        + (control_score * 0.25)
        + ((100 - risk) * 0.10)
        + (confidence * 0.10),
        2,
    )

    if stability_index >= 90:
        stability_state = "STABLE_GOLD"
    elif stability_index >= 80:
        stability_state = "STABLE_CONTROLLED"
    elif stability_index >= 65:
        stability_state = "WATCH"
    else:
        stability_state = "REVIEW_REQUIRED"

    return {
        "schema_version": "1.0.0",
        "index": "product-intelligence-governance-stability-index",
        "mode": "review_only",
        "stability_index": stability_index,
        "stability_state": stability_state,
        "inputs": {
            "consolidated_score": consolidated_score,
            "drift_score": drift_score,
            "control_score": control_score,
            "risk_percent": risk,
            "confidence_percent": confidence,
        },
        "signals": {
            "governance_state": snapshot.get("governance_state", "UNKNOWN"),
            "drift_state": drift.get("drift_state", "UNKNOWN"),
            "operational_state": tower.get("operational_state", "UNKNOWN"),
            "drift_count": drift.get("drift_count", 0),
            "warning_count": drift.get("warning_count", 0),
        },
        "next_recommended_increment": "Product Intelligence Governance Stabilization Gate",
    }


def write_reports(index: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-governance-stability-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    inputs = index["inputs"]
    signals = index["signals"]
    markdown = f"""# Product Intelligence Governance Stability Index

| Field | Value |
|---|---|
| Stability index | {index['stability_index']} |
| Stability state | {index['stability_state']} |
| Mode | {index['mode']} |

## Inputs

| Input | Value |
|---|---:|
| Consolidated score | {inputs['consolidated_score']} |
| Drift score | {inputs['drift_score']} |
| Control score | {inputs['control_score']} |
| Risk percent | {inputs['risk_percent']}% |
| Confidence percent | {inputs['confidence_percent']}% |

## Signals

| Signal | Value |
|---|---|
| Governance state | {signals['governance_state']} |
| Drift state | {signals['drift_state']} |
| Operational state | {signals['operational_state']} |
| Drift count | {signals['drift_count']} |
| Warning count | {signals['warning_count']} |

## Next increment

{index['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-governance-stability-index.md").write_text(markdown, encoding="utf-8")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Governance Stability Index</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}</style></head><body><h1>Product Intelligence Governance Stability Index</h1><div class="grid"><div class="card"><div class="label">Index</div><div class="metric">{index['stability_index']}</div></div><div class="card"><div class="label">State</div><div class="metric">{index['stability_state']}</div></div><div class="card"><div class="label">Risk</div><div class="metric">{inputs['risk_percent']}%</div></div><div class="card"><div class="label">Confidence</div><div class="metric">{inputs['confidence_percent']}%</div></div></div></body></html>"""
    (report_dir / "product-intelligence-governance-stability-index.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    index = build_index(report_dir)
    write_reports(index, report_dir)
    print(f"Governance stability index: {index['stability_state']} score={index['stability_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
