#!/usr/bin/env python3
"""Evaluate ReqSys delivery completion without fabricating formal approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

VALID_STATUSES = {"implemented", "partial", "gap"}
BLOCKING_CONCLUSIONS = {
    "failure",
    "timed_out",
    "action_required",
    "startup_failure",
}
IN_FLIGHT_STATUSES = {"queued", "in_progress", "pending", "requested", "waiting"}
REQUIRED_RUNTIME_PATHS = {
    "/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/liveness",
}


def load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_matrix(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("matrix must be a mapping")
    return payload


def latest_workflow_runs(runs: list[Any]) -> list[dict[str, Any]]:
    """Keep the newest run per workflow name; GitHub returns runs newest first."""
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        name = str(run.get("name") or "").strip()
        if name and name not in latest:
            latest[name] = run
    return list(latest.values())


def evaluate(
    matrix: dict[str, Any],
    operational: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls must be a list")

    findings: list[str] = []
    pending_formal: list[dict[str, Any]] = []
    status_counts = {status: 0 for status in sorted(VALID_STATUSES)}

    for control in controls:
        if not isinstance(control, dict):
            findings.append("invalid_control_entry")
            continue
        control_id = str(control.get("id") or "").strip()
        status = str(control.get("status") or "").strip().lower()
        if not control_id:
            findings.append("control_id_missing")
            continue
        if status not in VALID_STATUSES:
            findings.append(f"invalid_control_status:{control_id}")
            continue

        status_counts[status] += 1
        if status != "implemented":
            pending_formal.append(
                {
                    "control_id": control_id,
                    "status": status,
                    "priority": (
                        "P0"
                        if str(control.get("criticality") or "").lower() == "critical"
                        else "P1"
                    ),
                    "responsible_role": control.get("owner"),
                    "required_action": control.get("next_stage"),
                    "evidence_reference": control.get("evidence"),
                    "requires_real_authority": True,
                }
            )
        if control.get("production_touched") is True:
            findings.append(f"production_touched:{control_id}")

    open_prs = operational.get("open_prs") or []
    if not isinstance(open_prs, list):
        findings.append("open_prs_invalid")
        open_prs = []
    actionable_prs = [
        pr
        for pr in open_prs
        if isinstance(pr, dict)
        and pr.get("draft") is not True
        and str(pr.get("state") or "open").lower() == "open"
    ]

    runs = operational.get("workflow_runs") or []
    if not isinstance(runs, list):
        findings.append("workflow_runs_invalid")
        runs = []
    latest_runs = latest_workflow_runs(runs)
    failed_runs = [
        run
        for run in latest_runs
        if str(run.get("status") or "").lower() == "completed"
        and str(run.get("conclusion") or "").lower() in BLOCKING_CONCLUSIONS
    ]
    in_flight_runs = [
        run
        for run in latest_runs
        if str(run.get("status") or "").lower() in IN_FLIGHT_STATUSES
    ]

    endpoints = runtime.get("endpoints") or []
    if not isinstance(endpoints, list):
        findings.append("runtime_endpoints_invalid")
        endpoints = []
    by_path = {
        str(item.get("name") or item.get("path") or ""): item
        for item in endpoints
        if isinstance(item, dict)
    }
    runtime_missing = sorted(REQUIRED_RUNTIME_PATHS - set(by_path))
    runtime_failed = sorted(
        path
        for path in REQUIRED_RUNTIME_PATHS & set(by_path)
        if by_path[path].get("ok") is not True
    )
    runtime_ready = not runtime_missing and not runtime_failed

    no_gaps = status_counts["gap"] == 0
    technical_ready = not findings and no_gaps and not failed_runs and runtime_ready
    formal_ready = not pending_formal
    integration_ready = not actionable_prs
    delivered = technical_ready and formal_ready and integration_ready

    if delivered:
        phase = "DELIVERED"
    elif not technical_ready:
        phase = "TECHNICAL_REMEDIATION"
    elif not formal_ready:
        phase = "FORMAL_COMPLETION"
    else:
        phase = "DELIVERY_FINALIZATION"

    automatic_actions: list[str] = []
    if failed_runs:
        automatic_actions.append("rerun_or_remediate_failed_workflows")
    if runtime_missing or runtime_failed:
        automatic_actions.append("restore_runtime_and_regenerate_smoke_evidence")
    if pending_formal:
        automatic_actions.append("sync_formal_action_issues_and_escalations")
    if actionable_prs:
        automatic_actions.append("continue_governed_pr_and_merge_queue_processing")
    if in_flight_runs:
        automatic_actions.append("observe_in_flight_workflows_without_false_blocking")
    if not delivered:
        automatic_actions.append("refresh_delivery_completion_evidence_hourly")

    human_actions = [
        {
            "control_id": item["control_id"],
            "responsible_role": item["responsible_role"],
            "required_action": item["required_action"],
            "personal_assignee": None,
            "approval_reference": None,
            "reason_not_automated": "formal_authority_must_be_real_and_accountable",
        }
        for item in pending_formal
    ]

    return {
        "schema_version": "1.1.0",
        "contract": "reqsys-delivery-completion-controller",
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": phase,
        "delivered": delivered,
        "production_release_allowed": delivered,
        "technical_ready": technical_ready,
        "formal_ready": formal_ready,
        "integration_ready": integration_ready,
        "status_counts": status_counts,
        "summary": {
            "total_controls": sum(status_counts.values()),
            "pending_formal_controls": len(pending_formal),
            "actionable_open_prs": len(actionable_prs),
            "failed_workflows": len(failed_runs),
            "in_flight_workflows": len(in_flight_runs),
            "runtime_missing_endpoints": len(runtime_missing),
            "runtime_failed_endpoints": len(runtime_failed),
        },
        "pending_formal_controls": pending_formal,
        "failed_workflows": failed_runs,
        "in_flight_workflows": in_flight_runs,
        "runtime": {
            "ready": runtime_ready,
            "missing_endpoints": runtime_missing,
            "failed_endpoints": runtime_failed,
        },
        "automatic_actions": sorted(set(automatic_actions)),
        "human_actions": human_actions,
        "findings": sorted(set(findings)),
        "human_authority_substitution_allowed": False,
        "production_touched": False,
        "next_stage": (
            "archive_delivery_evidence_and_close_control_plane"
            if delivered
            else "execute_automatic_actions_and_complete_real_formal_authority_actions"
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# ReqSys Delivery Completion Controller",
        "",
        f"- Phase: **{report['phase']}**",
        f"- Delivered: **{str(report['delivered']).lower()}**",
        f"- Technical ready: **{str(report['technical_ready']).lower()}**",
        f"- Formal ready: **{str(report['formal_ready']).lower()}**",
        f"- Integration ready: **{str(report['integration_ready']).lower()}**",
        f"- Production release allowed: **{str(report['production_release_allowed']).lower()}**",
        "",
        "## Counters",
        "",
        f"- Pending formal controls: **{summary['pending_formal_controls']}**",
        f"- Actionable open PRs: **{summary['actionable_open_prs']}**",
        f"- Failed workflows: **{summary['failed_workflows']}**",
        f"- In-flight workflows: **{summary['in_flight_workflows']}**",
        f"- Runtime missing endpoints: **{summary['runtime_missing_endpoints']}**",
        f"- Runtime failed endpoints: **{summary['runtime_failed_endpoints']}**",
        "",
        "## Automatic actions",
        "",
    ]
    lines.extend(f"- `{action}`" for action in report["automatic_actions"])
    lines.extend(
        [
            "",
            "## Governance boundary",
            "",
            "- Formal authority substitution allowed: **false**",
            "- Production touched: **false**",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--operational", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    matrix = load_matrix(args.matrix)
    report = evaluate(matrix, load_json(args.operational), load_json(args.runtime))
    report["matrix_sha256"] = hashlib.sha256(args.matrix.read_bytes()).hexdigest()

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"phase": report["phase"], "delivered": report["delivered"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
