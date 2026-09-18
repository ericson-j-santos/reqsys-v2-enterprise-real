#!/usr/bin/env python3
"""Generate Product Intelligence release evidence pack.

The evidence pack consolidates governed artifacts for human review before release.
It is review-only and never deploys, mutates production, creates issues, calls
external AI providers or executes agents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

REQUIRED_ARTIFACTS = [
    "requirement-quality-score.json",
    "functional-traceability-graph.json",
    "reqsys-product-intelligence-dashboard.json",
    "product-decision-intelligence.json",
    "reqsys-product-intelligence-living-backlog.json",
    "product-intelligence-backlog-publisher-manifest.json",
    "product-intelligence-backlog-governance-gate.json",
    "product-intelligence-functional-roadmap.json",
    "product-intelligence-runtime-readiness-gate.json",
    "product-intelligence-runtime-planning-package.json",
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


def build_pack(report_dir: Path) -> dict[str, Any]:
    artifacts = {name: read_json(report_dir / name) for name in REQUIRED_ARTIFACTS}
    missing = [name for name, payload in artifacts.items() if not payload]

    quality = artifacts["requirement-quality-score.json"]
    traceability = artifacts["functional-traceability-graph.json"].get("summary", {})
    dashboard = artifacts["reqsys-product-intelligence-dashboard.json"]
    decision = artifacts["product-decision-intelligence.json"]
    readiness = artifacts["product-intelligence-runtime-readiness-gate.json"]
    planning = artifacts["product-intelligence-runtime-planning-package.json"]
    backlog_gate = artifacts["product-intelligence-backlog-governance-gate.json"]

    blockers: list[str] = []
    warnings: list[str] = []

    if missing:
        blockers.append("missing required artifacts: " + ", ".join(missing))
    if backlog_gate.get("gate_status") != "PASS":
        blockers.append("backlog governance gate must pass")
    if readiness.get("gate_status") != "PASS":
        blockers.append("runtime readiness gate must pass")
    if decision.get("human_review_required") is not True:
        blockers.append("human review must be required")
    if planning.get("governance", {}).get("production_mutation") != "disabled":
        blockers.append("production mutation must remain disabled")
    if planning.get("governance", {}).get("agent_execution") != "disabled":
        blockers.append("agent execution must remain disabled")

    if dashboard.get("product_readiness") != "READY_FOR_IMPLEMENTATION":
        warnings.append("product readiness is not READY_FOR_IMPLEMENTATION")
    if decision.get("decision") != "PROCEED_TO_GOVERNED_IMPLEMENTATION":
        warnings.append("decision does not recommend governed implementation")

    evidence_score = 100
    evidence_score -= len(blockers) * 30
    evidence_score -= len(warnings) * 10
    evidence_score = max(0, min(100, evidence_score))

    return {
        "schema_version": "1.0.0",
        "pack": "product-intelligence-release-evidence-pack",
        "mode": "review_only",
        "release_evidence_status": "PASS" if not blockers else "FAIL",
        "evidence_score": evidence_score,
        "risk_level": "LOW" if evidence_score >= 85 else "MEDIUM" if evidence_score >= 60 else "HIGH",
        "artifact_count": len(REQUIRED_ARTIFACTS) - len(missing),
        "required_artifact_count": len(REQUIRED_ARTIFACTS),
        "missing_artifacts": missing,
        "signals": {
            "quality_score": quality.get("final_score", 0),
            "traceability_coverage": traceability.get("traceability_coverage_score", 0),
            "product_readiness": dashboard.get("product_readiness", "UNKNOWN"),
            "decision": decision.get("decision", "UNKNOWN"),
            "runtime_readiness": readiness.get("runtime_readiness", "UNKNOWN"),
            "planning_status": planning.get("plan_status", "UNKNOWN"),
        },
        "blockers": blockers,
        "warnings": warnings,
        "governance": {
            "external_write": "disabled",
            "agent_execution": "disabled",
            "production_mutation": "disabled",
            "external_ai_call": "disabled",
            "human_review_required": True,
            "ci_green_required": True,
        },
    }


def write_reports(pack: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-release-evidence-pack.json").write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    blockers = "\n".join(f"- {item}" for item in pack["blockers"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in pack["warnings"]) or "- None"
    signals = pack["signals"]
    markdown = f"""# Product Intelligence Release Evidence Pack

| Field | Value |
|---|---|
| Release evidence status | {pack['release_evidence_status']} |
| Evidence score | {pack['evidence_score']} |
| Risk level | {pack['risk_level']} |
| Artifacts | {pack['artifact_count']} / {pack['required_artifact_count']} |
| Mode | {pack['mode']} |

## Signals

| Signal | Value |
|---|---|
| Quality score | {signals['quality_score']} |
| Traceability coverage | {signals['traceability_coverage']} |
| Product readiness | {signals['product_readiness']} |
| Decision | {signals['decision']} |
| Runtime readiness | {signals['runtime_readiness']} |
| Planning status | {signals['planning_status']} |

## Blockers

{blockers}

## Warnings

{warnings}

## Governance

- External write: disabled
- Agent execution: disabled
- Production mutation: disabled
- External AI call: disabled
- Human review required: true
- CI green required: true
"""
    (report_dir / "product-intelligence-release-evidence-pack.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Release Evidence Pack</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:30px;font-weight:bold;margin-top:8px;color:#22c55e}}
.section{{margin-top:28px}}
pre{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px;white-space:pre-wrap}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Release Evidence Pack</h1>
<div class="grid">
<div class="card"><div class="label">Status</div><div class="metric">{pack['release_evidence_status']}</div></div>
<div class="card"><div class="label">Evidence Score</div><div class="metric">{pack['evidence_score']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{pack['risk_level']}</div></div>
<div class="card"><div class="label">Artifacts</div><div class="metric">{pack['artifact_count']}/{pack['required_artifact_count']}</div></div>
</div>
<div class="section"><h2>Blockers</h2><pre>{blockers}</pre></div>
<div class="section"><h2>Warnings</h2><pre>{warnings}</pre></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-release-evidence-pack.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        pack = build_pack(report_dir)
        write_reports(pack, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Release evidence pack: {pack['release_evidence_status']} score={pack['evidence_score']}")
    if pack["release_evidence_status"] != "PASS":
        for blocker in pack["blockers"]:
            print(f"BLOCKER: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
