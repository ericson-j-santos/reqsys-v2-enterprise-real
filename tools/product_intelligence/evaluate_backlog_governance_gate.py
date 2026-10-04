#!/usr/bin/env python3
"""Evaluate governed gates for ReqSys Product Intelligence backlog publishing.

The gate evaluates the review package produced by the governed publisher. It does
not publish, write to external systems or execute agents. It only emits a gate
result and exits non-zero for unsafe publication packages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"
MANIFEST_NAME = "product-intelligence-backlog-publisher-manifest.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"manifest not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"json root must be object: {path}")
    return value


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    warnings: list[str] = []

    if manifest.get("external_write") != "disabled":
        violations.append("external_write must remain disabled")
    if manifest.get("agent_execution") != "disabled":
        violations.append("agent_execution must remain disabled")
    if manifest.get("requires_manual_approval") is not True:
        violations.append("requires_manual_approval must be true")

    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    if not items:
        warnings.append("no backlog items available for review")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            violations.append(f"item[{index}] must be an object")
            continue
        if item.get("human_review_required") is not True:
            violations.append(f"item[{index}].human_review_required must be true")
        if not item.get("id"):
            violations.append(f"item[{index}].id is required")
        if item.get("priority") not in {"P0", "P1", "P2"}:
            violations.append(f"item[{index}].priority must be P0, P1 or P2")
        if item.get("status") != "candidate":
            warnings.append(f"item[{index}].status is not candidate")

    priority_counts = manifest.get("priority_counts") if isinstance(manifest.get("priority_counts"), dict) else {}
    p0_count = int(priority_counts.get("P0") or 0)
    if p0_count > 0 and manifest.get("recommended_destination") != "critical_product_backlog_review":
        violations.append("P0 items must route to critical_product_backlog_review")

    gate_status = "PASS" if not violations else "FAIL"
    risk_level = "LOW"
    if violations:
        risk_level = "HIGH"
    elif warnings:
        risk_level = "MEDIUM"

    return {
        "schema_version": "1.0.0",
        "gate": "product-intelligence-backlog-governance-gate",
        "gate_status": gate_status,
        "risk_level": risk_level,
        "violations": violations,
        "warnings": warnings,
        "external_write": manifest.get("external_write"),
        "agent_execution": manifest.get("agent_execution"),
        "requires_manual_approval": manifest.get("requires_manual_approval"),
        "recommended_destination": manifest.get("recommended_destination"),
        "items_count": len(items),
        "priority_counts": priority_counts,
    }


def write_reports(result: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-backlog-governance-gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    violations = "\n".join(f"- {item}" for item in result["violations"]) or "- None"
    warnings = "\n".join(f"- {item}" for item in result["warnings"]) or "- None"
    markdown = f"""# Product Intelligence Backlog Governance Gate

| Field | Value |
|---|---|
| Gate status | {result['gate_status']} |
| Risk level | {result['risk_level']} |
| External write | {result['external_write']} |
| Agent execution | {result['agent_execution']} |
| Manual approval required | {result['requires_manual_approval']} |
| Recommended destination | {result['recommended_destination']} |
| Items | {result['items_count']} |

## Violations

{violations}

## Warnings

{warnings}
"""
    (report_dir / "product-intelligence-backlog-governance-gate.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Backlog Governance Gate</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:32px;font-weight:bold;margin-top:8px;color:#22c55e}}
.section{{margin-top:28px}}
pre{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px;white-space:pre-wrap}}
</style>
</head>
<body>
<div class="container">
<h1>Product Intelligence Backlog Governance Gate</h1>
<div class="grid">
<div class="card"><div class="label">Gate Status</div><div class="metric">{result['gate_status']}</div></div>
<div class="card"><div class="label">Risk Level</div><div class="metric">{result['risk_level']}</div></div>
<div class="card"><div class="label">External Write</div><div class="metric">{result['external_write']}</div></div>
<div class="card"><div class="label">Agent Execution</div><div class="metric">{result['agent_execution']}</div></div>
</div>
<div class="section"><h2>Violations</h2><pre>{violations}</pre></div>
<div class="section"><h2>Warnings</h2><pre>{warnings}</pre></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-backlog-governance-gate.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        manifest = read_json(report_dir / MANIFEST_NAME)
        result = evaluate(manifest)
        write_reports(result, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Backlog governance gate: {result['gate_status']} ({result['risk_level']})")
    if result["gate_status"] != "PASS":
        for violation in result["violations"]:
            print(f"VIOLATION: {violation}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
