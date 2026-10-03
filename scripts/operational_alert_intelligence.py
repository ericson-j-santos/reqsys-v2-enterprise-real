#!/usr/bin/env python3
"""Operational Alert Intelligence — classificação governada de alertas (report-only)."""

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
        "Workflow Reliability Analytics",
        "Operational Stability Score",
        "CI Incident Intelligence",
        "Post Merge Operational Summary",
    }
)


def classify_alert(workflow_name: str, conclusion: str) -> dict[str, Any]:
    alert_level = "INFO"
    alert_type = "OPERATIONAL_SIGNAL"
    noise_level = "LOW"
    action_policy = "OBSERVE"
    should_alert = True

    if workflow_name in INFORMATIVE_WORKFLOWS:
        alert_type = "INFORMATIVE_EVIDENCE"
        noise_level = "SUPPRESSED"
        if conclusion == "success":
            should_alert = False
        else:
            alert_level = "LOW"
            action_policy = "VERIFY_CONTEXT"

    if should_alert and conclusion not in {"", "success"}:
        alert_level = "HIGH"
        alert_type = "POTENTIAL_REGRESSION"
        action_policy = "MANUAL_REVIEW_REQUIRED"

    if conclusion == "cancelled":
        alert_level = "MEDIUM"
        alert_type = "CANCELLED_RUN"
        action_policy = "VERIFY_CONTEXT"

    return {
        "should_alert": should_alert,
        "alert_level": alert_level,
        "alert_type": alert_type,
        "noise_level": noise_level,
        "action_policy": action_policy,
    }


def build_recommendation(alert_level: str, alert_type: str) -> str:
    if alert_level == "HIGH":
        return (
            "Inspect failed workflow, correlate with recent PRs, "
            "avoid retry storms, and preserve mandatory gates."
        )
    if alert_type == "CANCELLED_RUN":
        return "Confirm whether cancellation was intentional, superseded, or caused by concurrency."
    if alert_type == "INFORMATIVE_EVIDENCE":
        return "Informative evidence only — no operational intervention required."
    return "No intervention required. Keep monitoring operational trend."


def build_payload(
    workflow_name: str,
    conclusion: str,
    *,
    branch: str = "main",
    commit: str = "",
    workflow_url: str = "",
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = classification or classify_alert(workflow_name, conclusion)
    recommendation = build_recommendation(cls["alert_level"], cls["alert_type"])
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "operational-alert-intelligence",
        "status": "ACTIVE" if cls["should_alert"] else "SUPPRESSED",
        "confidence_level": "HIGH",
        "maturity_percent": 85.0 if cls["should_alert"] else 100.0,
        "operational_risk": cls["alert_level"],
        "commit_sha": commit,
        "alert_intelligence": "ACTIVE",
        "workflow": workflow_name,
        "conclusion": conclusion,
        "branch": branch,
        "commit": commit,
        "workflow_url": workflow_url,
        "alert_level": cls["alert_level"],
        "alert_type": cls["alert_type"],
        "noise_level": cls["noise_level"],
        "action_policy": cls["action_policy"],
        "should_alert": cls["should_alert"],
        "recommendation": recommendation,
        "governance": {
            "noise_suppression": cls["alert_type"] == "INFORMATIVE_EVIDENCE",
            "mandatory_gates_preserved": True,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Operational Alert Intelligence",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Workflow | {payload['workflow']} |",
            f"| Conclusion | {payload['conclusion']} |",
            f"| Branch | {payload['branch']} |",
            f"| Commit | {payload['commit']} |",
            f"| Alert level | {payload['alert_level']} |",
            f"| Alert type | {payload['alert_type']} |",
            f"| Noise level | {payload['noise_level']} |",
            f"| Action policy | {payload['action_policy']} |",
            "",
            "## Recommendation",
            "",
            payload["recommendation"],
            "",
            "## Workflow link",
            "",
            payload.get("workflow_url") or "n/a",
        ]
    )


def render_html(payload: dict[str, Any]) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Operational Alert Intelligence</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.title{{font-size:32px;font-weight:bold;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:22px}}
.label{{color:#94a3b8;font-size:14px}}.metric{{font-size:34px;font-weight:bold;margin-top:10px}}
</style>
</head>
<body>
<div class="container">
<div class="title">Operational Alert Intelligence</div>
<div class="grid">
<div class="card"><div class="label">Alert Level</div><div class="metric">{payload['alert_level']}</div></div>
<div class="card"><div class="label">Alert Type</div><div class="metric">{payload['alert_type']}</div></div>
<div class="card"><div class="label">Noise Level</div><div class="metric">{payload['noise_level']}</div></div>
<div class="card"><div class="label">Action Policy</div><div class="metric">{payload['action_policy']}</div></div>
</div>
<p>{payload['recommendation']}</p>
</div>
</body>
</html>"""


def write_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "operational-alert-intelligence.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "operational-alert-intelligence.md").write_text(render_markdown(payload), encoding="utf-8")
    (output_dir / "operational-alert-intelligence.html").write_text(render_html(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operational Alert Intelligence generator")
    parser.add_argument("--workflow", default="manual")
    parser.add_argument("--conclusion", default="success")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--commit", default="")
    parser.add_argument("--workflow-url", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-alert-intelligence"))
    args = parser.parse_args(argv)

    payload = build_payload(
        args.workflow,
        args.conclusion,
        branch=args.branch,
        commit=args.commit,
        workflow_url=args.workflow_url,
    )
    write_report(payload, args.out_dir)
    print(f"Operational Alert Intelligence: level={payload['alert_level']} type={payload['alert_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
