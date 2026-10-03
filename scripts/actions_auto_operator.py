#!/usr/bin/env python3
"""GitHub Actions Auto Operator.

Verifica runs recentes da branch principal e executa rerun automático apenas
para workflows allowlisted e conclusões consideradas transitórias.
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
    "Main Post-Merge Validation",
    "PR CI Watch",
    "PR Conflict Guard",
    "Branch Protection Audit",
    "Fast CI - Operational Guardrails",
    "Workflow Command Center",
}

TRANSIENT_CONCLUSIONS = {"cancelled", "timed_out", "action_required"}
BLOCKED_CONCLUSIONS = {"failure"}


@dataclass(frozen=True)
class ActionRun:
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
    rerun_allowed: bool
    rerun_reason: str


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


def fetch_recent_runs(repo: str, token: str, branch: str, limit: int) -> list[ActionRun]:
    response = github_request(
        "GET",
        repo_api(repo, f"actions/runs?branch={branch}&per_page={limit}"),
        token,
    )
    runs: list[ActionRun] = []
    for item in response.get("workflow_runs", []):
        name = item.get("name") or ""
        conclusion = item.get("conclusion")
        status = item.get("status") or "unknown"
        allowed = (
            name in ALLOWLISTED_WORKFLOWS
            and status == "completed"
            and conclusion in TRANSIENT_CONCLUSIONS
        )
        if name not in ALLOWLISTED_WORKFLOWS:
            reason = "workflow_not_allowlisted"
        elif status != "completed":
            reason = "workflow_not_completed"
        elif conclusion in TRANSIENT_CONCLUSIONS:
            reason = "transient_conclusion_allowlisted"
        elif conclusion in BLOCKED_CONCLUSIONS:
            reason = "real_failure_requires_code_or_manual_analysis"
        else:
            reason = "no_rerun_needed"

        runs.append(
            ActionRun(
                id=int(item.get("id") or 0),
                name=name,
                status=status,
                conclusion=conclusion,
                event=item.get("event") or "unknown",
                branch=item.get("head_branch"),
                sha=item.get("head_sha"),
                url=item.get("html_url") or "",
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                rerun_allowed=allowed,
                rerun_reason=reason,
            )
        )
    return runs


def rerun_failed_jobs(repo: str, token: str, run_id: int) -> None:
    github_request(
        "POST",
        repo_api(repo, f"actions/runs/{run_id}/rerun-failed-jobs"),
        token,
    )


def build_report(runs: list[ActionRun], execute: bool, repo: str, branch: str) -> dict[str, Any]:
    candidates = [run for run in runs if run.rerun_allowed]
    blocked = [run for run in runs if run.conclusion in BLOCKED_CONCLUSIONS]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "execute" if execute else "dry_run",
        "allowlisted_workflows": sorted(ALLOWLISTED_WORKFLOWS),
        "transient_conclusions": sorted(TRANSIENT_CONCLUSIONS),
        "rerun_candidates": [asdict(run) for run in candidates],
        "blocked_failures": [asdict(run) for run in blocked],
        "recent_runs": [asdict(run) for run in runs],
        "summary": {
            "recent_runs": len(runs),
            "rerun_candidates": len(candidates),
            "blocked_failures": len(blocked),
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "actions-auto-operator.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Actions Auto Operator",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Mode: `{report['mode']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Recent runs: `{report['summary']['recent_runs']}`",
        f"- Rerun candidates: `{report['summary']['rerun_candidates']}`",
        f"- Blocked failures: `{report['summary']['blocked_failures']}`",
        "",
        "## Rerun candidates",
        "",
    ]
    if report["rerun_candidates"]:
        for run in report["rerun_candidates"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['conclusion']}` — run `{run['id']}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Blocked failures", ""])
    if report["blocked_failures"]:
        for run in report["blocked_failures"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['conclusion']}` — requires diagnosis")
    else:
        lines.append("- None")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed GitHub Actions auto operator.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-dir", default="artifacts/actions-auto-operator")
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
    report = build_report(runs, args.execute, args.repo, args.branch)

    executed: list[dict[str, Any]] = []
    if args.execute:
        for run in runs:
            if run.rerun_allowed:
                rerun_failed_jobs(args.repo, token, run.id)
                executed.append({"run_id": run.id, "workflow": run.name, "url": run.url})
    report["executed_reruns"] = executed

    write_report(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
