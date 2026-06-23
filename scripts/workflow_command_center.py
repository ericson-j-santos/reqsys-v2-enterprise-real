#!/usr/bin/env python3
"""Workflow Command Center for ReqSys.

Monitors recent GitHub Actions workflow runs and optionally dispatches
allowlisted workflows in a governed, auditable way.
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

ALLOWLISTED_WORKFLOWS = {
    "main-smoke-ci.yml",
    "main-operational-health.yml",
    "pr-ci-watch.yml",
    "ci-fast-operational.yml",
}

CRITICAL_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "CI Enterprise Fast",
    "Fast CI - Operational Guardrails",
    "Governance Quality Gates",
    "Branch Protection Audit",
    "PR Conflict Guard",
    "Main Smoke CI",
    "Main Operational Health",
}


@dataclass(frozen=True)
class WorkflowRunSummary:
    id: int
    name: str
    status: str
    conclusion: str | None
    event: str
    branch: str | None
    commit_sha: str | None
    url: str
    created_at: str | None
    updated_at: str | None


def _github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
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
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API URL is controlled by this script.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def _repo_api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def fetch_recent_runs(repo: str, token: str, branch: str, limit: int) -> list[WorkflowRunSummary]:
    response = _github_request(
        "GET",
        _repo_api(repo, f"actions/runs?branch={branch}&per_page={limit}"),
        token,
    )
    runs = []
    for run in response.get("workflow_runs", []):
        runs.append(
            WorkflowRunSummary(
                id=run["id"],
                name=run.get("name") or "",
                status=run.get("status") or "unknown",
                conclusion=run.get("conclusion"),
                event=run.get("event") or "unknown",
                branch=run.get("head_branch"),
                commit_sha=run.get("head_sha"),
                url=run.get("html_url") or "",
                created_at=run.get("created_at"),
                updated_at=run.get("updated_at"),
            )
        )
    return runs


def dispatch_workflow(repo: str, token: str, workflow_file: str, ref: str) -> dict[str, Any]:
    if workflow_file not in ALLOWLISTED_WORKFLOWS:
        raise ValueError(
            f"Workflow '{workflow_file}' is not allowlisted. Allowed: {sorted(ALLOWLISTED_WORKFLOWS)}"
        )
    _github_request(
        "POST",
        _repo_api(repo, f"actions/workflows/{workflow_file}/dispatches"),
        token,
        {"ref": ref},
    )
    return {"workflow_file": workflow_file, "ref": ref, "dispatched": True}


def build_report(runs: list[WorkflowRunSummary], dispatched: dict[str, Any] | None) -> dict[str, Any]:
    critical = [run for run in runs if run.name in CRITICAL_WORKFLOWS]
    failed = [run for run in critical if run.conclusion in {"failure", "cancelled", "timed_out", "action_required"}]
    pending = [run for run in critical if run.status != "completed"]
    missing = sorted(CRITICAL_WORKFLOWS - {run.name for run in runs})
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "critical_workflows_observed": len(critical),
        "failed_critical_workflows": [asdict(run) for run in failed],
        "pending_critical_workflows": [asdict(run) for run in pending],
        "missing_from_recent_window": missing,
        "recent_runs": [asdict(run) for run in runs],
        "dispatch": dispatched,
        "status": "attention" if failed or pending else "ok",
    }


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "workflow-command-center.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Workflow Command Center",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Summary",
        "",
        f"- Critical workflows observed: `{report['critical_workflows_observed']}`",
        f"- Failed critical workflows: `{len(report['failed_critical_workflows'])}`",
        f"- Pending critical workflows: `{len(report['pending_critical_workflows'])}`",
        f"- Missing from recent window: `{len(report['missing_from_recent_window'])}`",
        "",
    ]
    if report.get("dispatch"):
        lines.extend(["## Dispatch", "", f"```json\n{json.dumps(report['dispatch'], indent=2)}\n```", ""])
    if report["failed_critical_workflows"]:
        lines.extend(["## Failed critical workflows", ""])
        for run in report["failed_critical_workflows"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['conclusion']}`")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor and optionally dispatch allowlisted workflows.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--dispatch", default="", help="Allowlisted workflow file to dispatch.")
    parser.add_argument("--dispatch-ref", default="main")
    parser.add_argument("--output-dir", default="artifacts/workflow-command-center")
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

    dispatched = None
    if args.dispatch:
        dispatched = dispatch_workflow(args.repo, token, args.dispatch, args.dispatch_ref)

    runs = fetch_recent_runs(args.repo, token, args.branch, args.limit)
    report = build_report(runs, dispatched)
    write_artifacts(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["failed_critical_workflows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
