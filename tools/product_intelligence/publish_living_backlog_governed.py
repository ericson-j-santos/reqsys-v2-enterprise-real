#!/usr/bin/env python3
"""Generate a governed publish package for ReqSys Product Intelligence backlog.

This publisher does not write to external systems. It creates a reviewable
publication package with issue-ready Markdown, Redmine-ready Markdown and a
publisher manifest for manual approval.
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


def publication_package(backlog: dict[str, Any]) -> dict[str, Any]:
    items = backlog.get("items") if isinstance(backlog.get("items"), list) else []
    priority_counts = {"P0": 0, "P1": 0, "P2": 0}
    for item in items:
        if isinstance(item, dict):
            priority = str(item.get("priority") or "P2")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

    requires_manual_approval = bool(items)
    recommended_destination = "manual_review_queue"
    if priority_counts.get("P0", 0) > 0:
        recommended_destination = "critical_product_backlog_review"
    elif priority_counts.get("P1", 0) > 0:
        recommended_destination = "product_refinement_backlog_review"

    return {
        "schema_version": "1.0.0",
        "publisher": "product-intelligence-backlog-publisher-governado",
        "mode": "review_package_only",
        "external_write": "disabled",
        "agent_execution": "disabled",
        "requires_manual_approval": requires_manual_approval,
        "recommended_destination": recommended_destination,
        "requirement_id": backlog.get("requirement_id", "unknown"),
        "product_readiness": backlog.get("product_readiness", "UNKNOWN"),
        "priority_counts": priority_counts,
        "items": items,
        "governance": backlog.get("governance", {}),
    }


def item_markdown(item: dict[str, Any]) -> str:
    criteria = item.get("acceptance_criteria") if isinstance(item.get("acceptance_criteria"), list) else []
    criteria_md = "\n".join(f"- [ ] {criterion}" for criterion in criteria)
    return f"""## {item.get('title', 'Backlog item')}

| Field | Value |
|---|---|
| ID | {item.get('id', 'unknown')} |
| Type | {item.get('type', 'unknown')} |
| Priority | {item.get('priority', 'P2')} |
| Status | {item.get('status', 'candidate')} |
| Human review required | {item.get('human_review_required', True)} |

### Reason

{item.get('reason', 'Review required.')}

### Acceptance criteria

{criteria_md or '- [ ] Review acceptance criteria.'}
"""


def write_reports(package: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "product-intelligence-backlog-publisher-manifest.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    items = [item for item in package.get("items", []) if isinstance(item, dict)]
    issue_ready = "# Product Intelligence Backlog Publication Package\n\n"
    issue_ready += f"Requirement: `{package['requirement_id']}`\n\n"
    issue_ready += f"Recommended destination: `{package['recommended_destination']}`\n\n"
    issue_ready += "## Items\n\n"
    issue_ready += "\n".join(item_markdown(item) for item in items)
    issue_ready += "\n\n## Governance\n\n"
    issue_ready += "- External write: disabled\n"
    issue_ready += "- Agent execution: disabled\n"
    issue_ready += "- Manual approval required: true\n"
    (report_dir / "product-intelligence-backlog-publisher-github-ready.md").write_text(issue_ready, encoding="utf-8")

    redmine_ready = issue_ready.replace("# Product Intelligence Backlog Publication Package", "# ReqSys Product Intelligence - Backlog Governado")
    (report_dir / "product-intelligence-backlog-publisher-redmine-ready.md").write_text(redmine_ready, encoding="utf-8")

    rows = "\n".join(
        f"| {item.get('id')} | {item.get('type')} | {item.get('priority')} | {item.get('status')} | {item.get('title')} |"
        for item in items
    ) or "| - | - | - | - | - |"
    summary = f"""# Product Intelligence Backlog Publisher Governado

| Field | Value |
|---|---|
| Requirement | {package['requirement_id']} |
| Product readiness | {package['product_readiness']} |
| Destination | {package['recommended_destination']} |
| External write | {package['external_write']} |
| Agent execution | {package['agent_execution']} |
| Manual approval required | {package['requires_manual_approval']} |

## Priority counts

| Priority | Count |
|---|---:|
| P0 | {package['priority_counts'].get('P0', 0)} |
| P1 | {package['priority_counts'].get('P1', 0)} |
| P2 | {package['priority_counts'].get('P2', 0)} |

## Items

| ID | Type | Priority | Status | Title |
|---|---|---|---|---|
{rows}
"""
    (report_dir / "product-intelligence-backlog-publisher-summary.md").write_text(summary, encoding="utf-8")

    html_rows = "".join(
        f"<tr><td>{item.get('id')}</td><td>{item.get('type')}</td><td>{item.get('priority')}</td><td>{item.get('status')}</td><td>{item.get('title')}</td></tr>"
        for item in items
    ) or "<tr><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>"
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Intelligence Backlog Publisher Governado</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
.title{{font-size:32px;font-weight:bold}}
.badge{{padding:10px 18px;border-radius:999px;background:#7c2d12;color:#fed7aa;font-weight:bold}}
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
<div class="header"><div class="title">Product Intelligence Backlog Publisher Governado</div><div class="badge">REVIEW PACKAGE ONLY</div></div>
<div class="grid">
<div class="card"><div class="label">Destination</div><div class="metric">{package['recommended_destination']}</div></div>
<div class="card"><div class="label">External Write</div><div class="metric">{package['external_write']}</div></div>
<div class="card"><div class="label">Agent Execution</div><div class="metric">{package['agent_execution']}</div></div>
<div class="card"><div class="label">Items</div><div class="metric">{len(items)}</div></div>
</div>
<div class="section"><h2>Items</h2><table><tr><th>ID</th><th>Type</th><th>Priority</th><th>Status</th><th>Title</th></tr>{html_rows}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "product-intelligence-backlog-publisher.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    try:
        backlog = read_json(report_dir / "reqsys-product-intelligence-living-backlog.json")
        package = publication_package(backlog)
        write_reports(package, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "Governed publication package generated: "
        f"{len(package.get('items', []))} items, destination {package['recommended_destination']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
