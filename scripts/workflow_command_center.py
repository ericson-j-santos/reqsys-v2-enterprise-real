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
from html import escape
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
    "Main Post-Merge Validation",
}

BLOCKING_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}


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


def _percent(part: int, total: int) -> float:
    return round((part / total) * 100, 2) if total else 0.0


def _status_label(run: WorkflowRunSummary) -> str:
    if run.status != "completed":
        return "pending"
    if run.conclusion == "success":
        return "success"
    if run.conclusion in BLOCKING_CONCLUSIONS:
        return "failure"
    return "non_blocking"


def _operational_score(total: int, success: int, failed_critical: int, pending_critical: int, missing_critical: int) -> int:
    score = 100
    score -= failed_critical * 25
    score -= pending_critical * 10
    score -= missing_critical * 5
    if total:
        score -= round((100 - _percent(success, total)) * 0.25)
    return max(0, min(100, int(score)))


def build_report(runs: list[WorkflowRunSummary], dispatched: dict[str, Any] | None) -> dict[str, Any]:
    critical = [run for run in runs if run.name in CRITICAL_WORKFLOWS]
    failed = [run for run in critical if run.conclusion in BLOCKING_CONCLUSIONS]
    pending = [run for run in critical if run.status != "completed"]
    missing = sorted(CRITICAL_WORKFLOWS - {run.name for run in runs})

    total = len(runs)
    success = sum(1 for run in runs if _status_label(run) == "success")
    failed_all = sum(1 for run in runs if _status_label(run) == "failure")
    pending_all = sum(1 for run in runs if _status_label(run) == "pending")
    non_blocking = sum(1 for run in runs if _status_label(run) == "non_blocking")
    operational_score = _operational_score(total, success, len(failed), len(pending), len(missing))

    metrics = {
        "total_runs": total,
        "success_runs": success,
        "failed_runs": failed_all,
        "pending_runs": pending_all,
        "non_blocking_runs": non_blocking,
        "success_rate_percent": _percent(success, total),
        "critical_observed_percent": _percent(len(critical), len(CRITICAL_WORKFLOWS)),
    }

    status = "attention" if failed or pending else "ok"
    if status == "ok" and operational_score < 90:
        status = "watch"

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "critical_workflows_observed": len(critical),
        "failed_critical_workflows": [asdict(run) for run in failed],
        "pending_critical_workflows": [asdict(run) for run in pending],
        "missing_from_recent_window": missing,
        "recent_runs": [asdict(run) | {"health": _status_label(run)} for run in runs],
        "dispatch": dispatched,
        "status": status,
        "operational_score": operational_score,
        "metrics": metrics,
    }


def _render_html(report: dict[str, Any]) -> str:
    rows = []
    for run in report["recent_runs"][:30]:
        rows.append(
            "<tr>"
            f"<td>{escape(run['health'])}</td>"
            f"<td><a href=\"{escape(run['url'])}\">{escape(run['name'])}</a></td>"
            f"<td>{escape(str(run['status']))}</td>"
            f"<td>{escape(str(run['conclusion']))}</td>"
            f"<td>{escape(str(run['event']))}</td>"
            f"<td>{escape(str(run['updated_at']))}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ReqSys Workflow Command Center</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 12px; padding: 16px; background: #f9fafb; }}
    .ok {{ color: #166534; }} .attention {{ color: #991b1b; }} .watch {{ color: #854d0e; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>ReqSys Workflow Command Center</h1>
  <p>Gerado em UTC: <strong>{escape(report['generated_at'])}</strong></p>
  <div class=\"grid\">
    <div class=\"card\"><strong>Status</strong><br><span class=\"{escape(report['status'])}\">{escape(report['status'])}</span></div>
    <div class=\"card\"><strong>Operational Score</strong><br>{report['operational_score']}/100</div>
    <div class=\"card\"><strong>Success rate</strong><br>{report['metrics']['success_rate_percent']}%</div>
    <div class=\"card\"><strong>Critical observed</strong><br>{report['metrics']['critical_observed_percent']}%</div>
    <div class=\"card\"><strong>Failed critical</strong><br>{len(report['failed_critical_workflows'])}</div>
    <div class=\"card\"><strong>Pending critical</strong><br>{len(report['pending_critical_workflows'])}</div>
  </div>
  <h2>Recent workflow runs</h2>
  <table>
    <thead><tr><th>Health</th><th>Workflow</th><th>Status</th><th>Conclusion</th><th>Event</th><th>Updated</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


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
        f"Operational score: `{report['operational_score']}/100`",
        "",
        "## Summary",
        "",
        f"- Critical workflows observed: `{report['critical_workflows_observed']}`",
        f"- Failed critical workflows: `{len(report['failed_critical_workflows'])}`",
        f"- Pending critical workflows: `{len(report['pending_critical_workflows'])}`",
        f"- Missing from recent window: `{len(report['missing_from_recent_window'])}`",
        f"- Success rate: `{report['metrics']['success_rate_percent']}%`",
        f"- Critical observed: `{report['metrics']['critical_observed_percent']}%`",
        "",
    ]
    if report.get("dispatch"):
        lines.extend(["## Dispatch", "", f"```json\n{json.dumps(report['dispatch'], indent=2)}\n```", ""])
    if report["failed_critical_workflows"]:
        lines.extend(["## Failed critical workflows", ""])
        for run in report["failed_critical_workflows"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['conclusion']}`")
    if report["pending_critical_workflows"]:
        lines.extend(["", "## Pending critical workflows", ""])
        for run in report["pending_critical_workflows"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['status']}`")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "workflow-command-center.html").write_text(_render_html(report), encoding="utf-8")


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
