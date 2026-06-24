#!/usr/bin/env python3
"""Evaluate Product Intelligence release governance gate.

This gate evaluates whether the release evidence pack is safe for human release
review. It never deploys, mutates production, creates issues, calls external AI
providers or executes agents.
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


def evaluate(report_dir: Path) -> dict[str, Any]:
    evidence = read_json(report_dir / "product-intelligence-release-evidence-pack.json")
    planning = read_json(report_dir / "product-intelligence-runtime-planning-package.json")
    readiness = read_json(report_dir / "product-intelligence-runtime-readiness-gate.json")

    blockers: list[str] = []
    warnings: list[str] = []

    evidence_status = evidence.get("release_evidence_status", "UNKNOWN")
    evidence_score = float(evidence.get("evidence_score") or 0)
    planning_status = planning.get("plan_status", "UNKNOWN")
    readiness_status = readiness.get("runtime_readiness", "UNKNOWN")

    evidence_governance = evidence.get("governance") if isinstance(evidence.get("governance"), dict) else {}
    planning_governance = planning.get("governance") if isinstance(planning.get("governance"), dict) else {}

    if evidence_status != "PASS":
        blockers.append("release evidence pack must pass")
    if evidence_score < 70:
        blockers.append("release evidence score must be at least 70")
    if evidence_governance.get("ci_green_required") is not True:
        blockers.append("ci_green_required must be true")
    if evidence_governance.get("human_review_required") is not True:
        blockers.append("human_review_required must be true")
    if planning_governance.get("production_mutation") != "disabled":
        blockers.append("production_mutation must remain disabled")
    if planning_governance.get("external_write") != "disabled":
        blockers.append("external_write must remain disabled")
    if planning_governance.get("agent_execution") != "disabled":
        blockers.append("agent_execution must remain disabled")
    if planning_governance.get("external_ai_call") != "disabled":
        blockers.append("external_ai_call must remain disabled")

    if planning_status != "ready_for_review":
        warnings.append(f"planning status is {planning_status}; release review should remain conservative")
    if readiness_status != "READY_FOR_GOVERNED_PLANNING":
        warnings.append(f"runtime readiness is {readiness_status}")

    gate_status = "PASS" if not blockers else "FAIL"
    release_review_state = "READY_FOR_HUMAN_RELEASE_REVIEW" if gate_status == "PASS" and not warnings else "READY_WITH_WARNINGS" if gate_status == "PASS" else "BLOCKED"
    risk_level = "LOW" if release_review_state == "READY_FOR_HUMAN_RELEASE_REVIEW" else "MEDIUM" if gate_status == "PASS" else "HIGH"

    return {
        "schema_version": "1.0.0",
        "gate": "product-intelligence-release-governance-gate",
        "gate_status": gate_status,
        "release_review_state": release_review_state,
        "risk_level": risk_level,
        "signals": {
            "release_evidence_status": evidence_status,
            "release_evidence_score": evidence_score,
            "planning_status": planning_status,
            "runtime_readiness": readiness_status,
        },
        "blockers": blockers,
        "warnings": warnings,
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "human_release_review_required": True,
        },
    }


def write_reports(result: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-release-governance-gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    blockers = "\n".join(f"- {item}" for item in result["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in result["warnings"]) or "- None"
    signals = result["signals"]
    markdown = f"""# Product Intelligence Release Governance Gate

| Field | Value |
|---|---|
| Gate status | {result['gate_status']} |
| Release review state | {result['release_review_state']} |
| Risk level | {result['risk_level']} |
| Evidence status | {signals['release_evidence_status']} |
| Evidence score | {signals['release_evidence_score']} |
| Planning status | {signals['planning_status']} |
| Runtime readiness | {signals['runtime_readiness']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Governance

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External AI call: disabled
- Human release review required: true
"""
    (report_dir / "product-intelligence-release-governance-gate.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Release Governance Gate</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:28px;font-weight:bold;margin-top:8px;color:#22c55e}}
.section{{margin-top:28px}}
pre{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px;white-space:pre-wrap}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Release Governance Gate</h1>
<div class="grid">
<div class="card"><div class="label">Gate</div><div class="metric">{result['gate_status']}</div></div>
<div class="card"><div class="label">Review State</div><div class="metric">{result['release_review_state']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{result['risk_level']}</div></div>
<div class="card"><div class="label">Evidence Score</div><div class="metric">{signals['release_evidence_score']}</div></div>
</div>
<div class="section"><h2>Blockers</h2><pre>{blockers}</pre></div>
<div class="section"><h2>Warnings</h2><pre>{warnings}</pre></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-release-governance-gate.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        result = evaluate(report_dir)
        write_reports(result, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Release governance gate: {result['gate_status']} ({result['release_review_state']})")
    if result["gate_status"] != "PASS":
        for blocker in result["blockers"]:
            print(f"BLOCKER: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
