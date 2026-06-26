#!/usr/bin/env python3
"""Runtime Health Validator for ReqSys operational governance.

Detecta estado operacional a partir dos runs recentes de GitHub Actions e gera
plano de remediacao governado sem executar mudancas por padrao.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

MATURITY_LEVELS = {
    "green": "managed",
    "yellow": "defined",
    "red": "reactive",
}

ENVIRONMENT_ENDPOINTS = {
    "dev": "https://reqsys-api-dev.fly.dev/health",
    "homolog": "https://reqsys-api-stg.fly.dev/health",
    "prod": "https://reqsys-api.fly.dev/health",
}

ALLOWLISTED_REMEDIATION_WORKFLOWS = {
    "Actions Auto Operator",
    "Operational Governance Orchestrator",
    "Main Post-Merge Validation",
    "PR CI Watch",
    "PR Conflict Guard",
    "Branch Protection Audit",
    "Fast CI - Operational Guardrails",
}

TRANSIENT_CONCLUSIONS = {"cancelled", "timed_out", "action_required"}
HARD_FAILURE_CONCLUSIONS = {"failure"}
SECURITY_KEYWORDS = ("security", "secret", "token", "permission", "branch protection", "governance")


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    event: str
    branch: str | None
    sha: str | None
    url: str
    created_at: str | None
    updated_at: str | None

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "pending"
        if self.conclusion == "success":
            return "green"
        if self.conclusion in TRANSIENT_CONCLUSIONS:
            return "yellow"
        if self.conclusion in HARD_FAILURE_CONCLUSIONS:
            return "red"
        return "unknown"

    @property
    def severity(self) -> str:
        lowered = self.name.lower()
        if self.health == "red" and any(keyword in lowered for keyword in SECURITY_KEYWORDS):
            return "critical"
        if self.health == "red":
            return "high"
        if self.health == "yellow":
            return "medium"
        if self.health == "pending":
            return "low"
        return "none"


def github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API URL is controlled.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def repo_api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def fetch_recent_runs(repo: str, token: str, branch: str, limit: int) -> list[WorkflowRun]:
    data = github_request("GET", repo_api(repo, f"actions/runs?branch={branch}&per_page={limit}"), token)
    return [
        WorkflowRun(
            id=int(item.get("id") or 0),
            name=item.get("name") or "workflow-desconhecido",
            status=item.get("status") or "unknown",
            conclusion=item.get("conclusion"),
            event=item.get("event") or "unknown",
            branch=item.get("head_branch"),
            sha=item.get("head_sha"),
            url=item.get("html_url") or "",
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
        )
        for item in data.get("workflow_runs", [])
    ]


def build_remediation_plan(runs: list[WorkflowRun]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for run in runs:
        if run.health == "yellow" and run.name in ALLOWLISTED_REMEDIATION_WORKFLOWS:
            plan.append(
                {
                    "run_id": run.id,
                    "workflow": run.name,
                    "action": "rerun_failed_jobs",
                    "allowed": True,
                    "reason": "transient_or_attention_state_allowlisted",
                    "severity": run.severity,
                    "url": run.url,
                }
            )
        elif run.health == "red":
            plan.append(
                {
                    "run_id": run.id,
                    "workflow": run.name,
                    "action": "manual_or_code_fix_required",
                    "allowed": False,
                    "reason": "real_failure_not_auto_remediated",
                    "severity": run.severity,
                    "url": run.url,
                }
            )
    return plan


def execute_plan(repo: str, token: str, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    executed: list[dict[str, Any]] = []
    for item in plan:
        if not item.get("allowed"):
            continue
        github_request("POST", repo_api(repo, f"actions/runs/{item['run_id']}/rerun-failed-jobs"), token)
        executed.append({**item, "executed": True})
    return executed


def build_backlog(runs: list[WorkflowRun], plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backlog: list[dict[str, Any]] = []
    for item in plan:
        if item.get("allowed"):
            backlog.append({
                "id": f"OPS-AUTO-{item['run_id']}",
                "type": "remediation",
                "priority": "P2" if item.get("severity") in {"medium", "low"} else "P1",
                "title": f"Executar remediação governada para {item['workflow']}",
                "evidence": item.get("url"),
                "suggested_action": item.get("action"),
            })
        else:
            backlog.append({
                "id": f"OPS-GAP-{item['run_id']}",
                "type": "gap",
                "priority": "P0" if item.get("severity") == "critical" else "P1",
                "title": f"Tratar falha não autocorrigível em {item['workflow']}",
                "evidence": item.get("url"),
                "suggested_action": "human_review_after_safe_auto_correction",
            })
    for run in runs:
        if run.health == "pending":
            backlog.append({
                "id": f"OPS-PENDING-{run.id}",
                "type": "monitoring",
                "priority": "P3",
                "title": f"Acompanhar workflow pendente {run.name}",
                "evidence": run.url,
                "suggested_action": "wait_for_ci_completion",
            })
    return backlog


def build_environment_sync() -> dict[str, Any]:
    return {
        "strategy": "dev_to_homolog_to_prod",
        "production_execution": "blocked_without_explicit_governed_promotion",
        "flyio_health_endpoints": ENVIRONMENT_ENDPOINTS,
        "required_evidence": ["health_check", "ci_green", "rollback_metadata", "change_ticket_for_prod"],
    }


def build_rollback_policy(state: str) -> dict[str, Any]:
    return {
        "status": "armed" if state in {"red", "yellow"} else "standby",
        "execution": "manual_approval_required",
        "automatic_destructive_actions": False,
        "safe_actions": ["rerun_failed_jobs_allowlisted", "publish_evidence", "open_backlog_gap"],
        "required_metadata": ["source_ref", "target_environment", "last_green_sha", "correlation_id"],
    }


def classify_maturity(state: str, runs: list[WorkflowRun], backlog: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "level": MATURITY_LEVELS.get(state, "unknown"),
        "state": state,
        "score": max(0, 100 - (35 if state == "red" else 15 if state == "yellow" else 0) - len(backlog) * 3),
        "signals": {
            "total_runs": len(runs),
            "automated_backlog_items": len(backlog),
            "has_critical_gap": any(item.get("priority") == "P0" for item in backlog),
        },
    }


def build_report(repo: str, branch: str, runs: list[WorkflowRun], plan: list[dict[str, Any]], executed: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    red = [run for run in runs if run.health == "red"]
    yellow = [run for run in runs if run.health == "yellow"]
    pending = [run for run in runs if run.health == "pending"]
    state = "red" if red else "yellow" if yellow or pending else "green"
    backlog = build_backlog(runs, plan)
    executive_status = "Runtime operacional saudável" if state == "green" else "Runtime requer acompanhamento governado" if state == "yellow" else "Runtime com bloqueios operacionais"
    return {
        "schema_version": "1.1.0",
        "correlation_id": str(uuid4()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": mode,
        "state": state,
        "executive_status": executive_status,
        "maturity": classify_maturity(state, runs, backlog),
        "summary": {
            "runs": len(runs),
            "green": sum(1 for run in runs if run.health == "green"),
            "yellow": len(yellow),
            "red": len(red),
            "pending": len(pending),
            "remediation_candidates": sum(1 for item in plan if item.get("allowed")),
            "blocked_remediations": sum(1 for item in plan if not item.get("allowed")),
            "executed_remediations": len(executed),
        },
        "runs": [asdict(run) | {"health": run.health, "severity": run.severity} for run in runs],
        "remediation_plan": plan,
        "executed_remediations": executed,
        "automatic_backlog": backlog,
        "regression_detection": {
            "enabled": True,
            "state": "regression_suspected" if red else "no_regression_detected",
            "failed_workflows": [run.name for run in red],
        },
        "environment_sync": build_environment_sync(),
        "rollback_policy": build_rollback_policy(state),
        "evidence_consolidation": {
            "artifact": "runtime-health-validator-evidence",
            "files": ["runtime-health-validator.json", "summary.md"],
            "dashboard_entrypoint": "summary.md",
        },
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "branch_protection_change": False,
            "secrets_change": False,
            "anti_loop": True,
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runtime-health-validator.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Runtime Health Validator",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Mode: `{report['mode']}`",
        f"- State: `{report['state']}`",
        f"- Executive status: `{report['executive_status']}`",
        f"- Maturity: `{report['maturity']['level']}` (`{report['maturity']['score']}`)",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report["summary"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Remediation plan", ""])
    if report["remediation_plan"]:
        for item in report["remediation_plan"]:
            lines.append(f"- `{item['action']}` · `{item['workflow']}` · allowed=`{item['allowed']}` · severity=`{item['severity']}` · [run]({item['url']})")
    else:
        lines.append("- None")
    lines.extend(["", "## Automatic backlog", ""])
    if report["automatic_backlog"]:
        for item in report["automatic_backlog"]:
            lines.append(f"- `{item['priority']}` · `{item['type']}` · {item['title']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Environment sync", ""])
    for env, endpoint in report["environment_sync"]["flyio_health_endpoints"].items():
        lines.append(f"- `{env}`: `{endpoint}`")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime health validator and governed remediation executor.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--mode", choices=["report_only", "dry_run", "execute"], default="report_only")
    parser.add_argument("--output-dir", default="artifacts/runtime-health-validator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    if not args.repo:
        print("--repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2
    runs = fetch_recent_runs(args.repo, token, args.branch, args.limit)
    plan = build_remediation_plan(runs)
    executed = execute_plan(args.repo, token, plan) if args.mode == "execute" else []
    report = build_report(args.repo, args.branch, runs, plan, executed, args.mode)
    write_report(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
