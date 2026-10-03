#!/usr/bin/env python3
"""Detect governance drift in Product Intelligence artifacts.

Review-only detector. It compares current KPIs and states with expected governed
thresholds and emits JSON, Markdown and HTML reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

THRESHOLDS = {
    "product_intelligence_maturity_percent": 90,
    "functional_governance_percent": 92,
    "release_evidence_percent": 88,
    "runtime_planning_percent": 80,
    "estimated_operational_risk_percent": 15,
    "statistical_confidence_percent": 80,
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_drift_report(report_dir: Path) -> dict[str, Any]:
    snapshot = read_json(report_dir / "product-intelligence-continuous-governance-snapshot.json")
    tower = read_json(report_dir / "product-intelligence-executive-control-tower.json")

    kpis = snapshot.get("kpis") if isinstance(snapshot.get("kpis"), dict) else {}
    signals = snapshot.get("signals") if isinstance(snapshot.get("signals"), dict) else {}

    drifts: list[dict[str, Any]] = []
    for key, threshold in THRESHOLDS.items():
        current = as_int(kpis.get(key), 0)
        if key == "estimated_operational_risk_percent":
            drift = current > threshold
            delta = current - threshold
            direction = "above_maximum"
        else:
            drift = current < threshold
            delta = threshold - current
            direction = "below_minimum"
        if drift:
            drifts.append({"metric": key, "current": current, "threshold": threshold, "delta": delta, "direction": direction})

    signal_warnings: list[str] = []
    if signals.get("release_gate_status") not in {"PASS", "UNKNOWN"}:
        signal_warnings.append("release gate is not PASS")
    if signals.get("release_evidence_status") not in {"PASS", "UNKNOWN"}:
        signal_warnings.append("release evidence is not PASS")

    drift_score = max(0, 100 - (len(drifts) * 12) - (len(signal_warnings) * 8))
    drift_state = "NO_DRIFT" if not drifts and not signal_warnings else "DRIFT_WITH_WARNINGS" if drift_score >= 70 else "DRIFT_REVIEW_REQUIRED"

    return {
        "schema_version": "1.0.0",
        "detector": "product-intelligence-governance-drift-detector",
        "mode": "review_only",
        "drift_state": drift_state,
        "drift_score": drift_score,
        "drift_count": len(drifts),
        "warning_count": len(signal_warnings),
        "thresholds": THRESHOLDS,
        "kpis": kpis,
        "signals": signals,
        "drifts": drifts,
        "warnings": signal_warnings,
        "control_score": tower.get("control_score", 0),
        "next_recommended_increment": "Product Intelligence Governance Stability Index",
    }


def write_reports(report: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-governance-drift-detector.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    drift_rows = "\n".join(
        f"| {item['metric']} | {item['current']} | {item['threshold']} | {item['delta']} | {item['direction']} |"
        for item in report["drifts"]
    ) or "| - | - | - | - | - |"
    warnings = "\n".join(f"- {item}" for item in report["warnings"]) or "- None"
    markdown = f"""# Product Intelligence Governance Drift Detector

| Field | Value |
|---|---|
| Drift state | {report['drift_state']} |
| Drift score | {report['drift_score']} |
| Drift count | {report['drift_count']} |
| Warning count | {report['warning_count']} |
| Control score | {report['control_score']} |
| Mode | {report['mode']} |

## Drifts

| Metric | Current | Threshold | Delta | Direction |
|---|---:|---:|---:|---|
{drift_rows}

## Warnings

{warnings}

## Next increment

{report['next_recommended_increment']}
"""
    (report_dir / "product-intelligence-governance-drift-detector.md").write_text(markdown, encoding="utf-8")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Governance Drift Detector</title><style>body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}.label{{color:#94a3b8}}.metric{{font-size:30px;font-weight:bold;color:#22c55e}}table{{width:100%;border-collapse:collapse;margin-top:16px}}td,th{{border-bottom:1px solid #1f2937;padding:12px;text-align:left}}</style></head><body><h1>Product Intelligence Governance Drift Detector</h1><div class="grid"><div class="card"><div class="label">State</div><div class="metric">{report['drift_state']}</div></div><div class="card"><div class="label">Score</div><div class="metric">{report['drift_score']}</div></div><div class="card"><div class="label">Drifts</div><div class="metric">{report['drift_count']}</div></div><div class="card"><div class="label">Warnings</div><div class="metric">{report['warning_count']}</div></div></div></body></html>"""
    (report_dir / "product-intelligence-governance-drift-detector.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    report = build_drift_report(report_dir)
    write_reports(report, report_dir)
    print(f"Governance drift detector: {report['drift_state']} score={report['drift_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
