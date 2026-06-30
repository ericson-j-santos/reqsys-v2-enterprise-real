#!/usr/bin/env python3
"""Unified Operational Event Bus — roteamento governado de eventos operacionais (report-only)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INFORMATIVE_WORKFLOWS = frozenset(
    {
        "Operational Runtime Mesh Hub",
        "Workflow Governance Consolidator",
        "Operational Intelligence Hub",
        "Operational Governance Orchestrator",
        "Coordenador Status Consolidator",
        "Runtime Health Validator",
        "Workflow Command Center",
        "Workflow Reliability Analytics",
        "Operational Stability Score",
        "CI Incident Intelligence",
        "Post Merge Operational Summary",
        "CI Observability",
    }
)


def classify_event(workflow_name: str, conclusion: str) -> dict[str, Any]:
    event_class = "OPERATIONAL_SIGNAL"
    severity = "INFO"
    action_policy = "OBSERVE"
    should_emit = True

    if workflow_name in INFORMATIVE_WORKFLOWS:
        event_class = "INFORMATIVE_EVIDENCE"
        severity = "INFO"
        action_policy = "OBSERVE"
        if conclusion in {"success", "skipped"}:
            should_emit = False

    if conclusion not in {"", "success", "skipped"} and event_class != "INFORMATIVE_EVIDENCE":
        event_class = "OPERATIONAL_INCIDENT"
        severity = "HIGH"
        action_policy = "MANUAL_REVIEW_REQUIRED"

    if conclusion == "cancelled":
        event_class = "OPERATIONAL_INTERRUPTION"
        severity = "MEDIUM"
        action_policy = "VERIFY_CONTEXT"

    routing_key = "ops.signal"
    if event_class == "OPERATIONAL_INCIDENT":
        routing_key = "ops.incident"
    elif event_class == "OPERATIONAL_INTERRUPTION":
        routing_key = "ops.interruption"
    elif event_class == "INFORMATIVE_EVIDENCE":
        routing_key = "ops.informative"

    return {
        "should_emit": should_emit,
        "event_class": event_class,
        "severity": severity,
        "action_policy": action_policy,
        "routing_key": routing_key,
    }


def build_payload(
    workflow_name: str,
    conclusion: str,
    *,
    branch: str = "main",
    commit: str = "",
    workflow_url: str = "",
    run_id: str = "",
    run_attempt: str = "1",
    event_name: str = "workflow_dispatch",
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = classification or classify_event(workflow_name, conclusion)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "unified-operational-event-bus",
        "status": "ACTIVE" if cls["should_emit"] else "SUPPRESSED",
        "confidence_level": "HIGH",
        "maturity_percent": 90.0 if cls["should_emit"] else 100.0,
        "operational_risk": cls["severity"],
        "commit_sha": commit,
        "bus": "unified-operational-event-bus",
        "bus_status": "ACTIVE",
        "event_class": cls["event_class"],
        "severity": cls["severity"],
        "routing_key": cls["routing_key"],
        "action_policy": cls["action_policy"],
        "should_emit": cls["should_emit"],
        "governance_gate": "PRESERVED",
        "source_workflow": {
            "platform": "github_actions",
            "workflow": workflow_name,
            "conclusion": conclusion,
            "event": event_name,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "workflow_url": workflow_url,
        },
        "git": {
            "branch": branch,
            "commit": commit,
        },
        "routing": {
            "dashboard": True,
            "history": True,
            "alerting": True,
            "remediation": False,
            "manual_review_required": cls["action_policy"],
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    src = payload["source_workflow"]
    return "\n".join(
        [
            "# Unified Operational Event Bus",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Bus status | {payload['bus_status']} |",
            f"| Workflow | {src['workflow']} |",
            f"| Conclusion | {src['conclusion']} |",
            f"| Event class | {payload['event_class']} |",
            f"| Severity | {payload['severity']} |",
            f"| Routing key | {payload['routing_key']} |",
            f"| Action policy | {payload['action_policy']} |",
            f"| Governance gate | {payload['governance_gate']} |",
            f"| Branch | {payload['git']['branch']} |",
            f"| Commit | {payload['git']['commit']} |",
            "",
            "## Source workflow",
            "",
            src.get("workflow_url") or "n/a",
        ]
    )


def render_html(payload: dict[str, Any]) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Unified Operational Event Bus</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.title{{font-size:32px;font-weight:bold;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:22px}}
.label{{color:#94a3b8;font-size:14px}}.metric{{font-size:32px;font-weight:bold;margin-top:10px}}
</style>
</head>
<body>
<div class="title">Unified Operational Event Bus</div>
<div class="grid">
<div class="card"><div class="label">Event Class</div><div class="metric">{payload['event_class']}</div></div>
<div class="card"><div class="label">Severity</div><div class="metric">{payload['severity']}</div></div>
<div class="card"><div class="label">Routing Key</div><div class="metric">{payload['routing_key']}</div></div>
</div>
</body>
</html>"""


def write_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "unified-operational-event.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "unified-operational-event-bus.md").write_text(render_markdown(payload), encoding="utf-8")
    (output_dir / "unified-operational-event-bus.html").write_text(render_html(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unified Operational Event Bus generator")
    parser.add_argument("--workflow", default="manual")
    parser.add_argument("--conclusion", default="success")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--commit", default="")
    parser.add_argument("--workflow-url", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="1")
    parser.add_argument("--event-name", default="workflow_dispatch")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/unified-operational-event-bus"))
    args = parser.parse_args(argv)

    payload = build_payload(
        args.workflow,
        args.conclusion,
        branch=args.branch,
        commit=args.commit,
        workflow_url=args.workflow_url,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        event_name=args.event_name,
    )
    write_report(payload, args.out_dir)
    print(
        f"Unified Operational Event Bus: class={payload['event_class']} "
        f"routing={payload['routing_key']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
