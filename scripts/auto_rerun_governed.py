#!/usr/bin/env python3
"""Governed Auto-Rerun for ReqSys GitHub Actions.

Classifies failed workflow runs and reruns only allowlisted transient failures.
It is intentionally conservative: deterministic failures remain blocked.
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
    "CI — ReqSys v2 Enterprise",
    "CI Enterprise Fast",
    "Main Smoke CI",
    "Main Operational Health",
    "Fast CI - Operational Guardrails",
}

BLOCKLISTED_KEYWORDS = {
    "governance",
    "governança",
    "security",
    "segurança",
    "branch protection",
    "compliance",
    "audit",
}

TRANSIENT_CONCLUSIONS = {"timed_out", "cancelled"}
TRANSIENT_LOG_HINTS = {
    "timeout",
    "timed out",
    "runner unavailable",
    "hosted runner",
    "artifact unavailable",
    "failed to download",
    "network",
    "connection reset",
    "502",
    "503",
    "504",
    "rate limit",
}

MAX_RERUN_ATTEMPTS = 2


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    run_attempt: int
    html_url: str
    head_branch: str | None
    head_sha: str | None
    event: str


@dataclass(frozen=True)
class RerunDecision:
    run_id: int
    workflow_name: str
    decision: str
    reason: str
    transient: bool
    allowlisted: bool
    blocked: bool
    run_attempt: int
    rerun_executed: bool = False


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
        with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled GitHub API URL.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def _repo_api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def fetch_recent_failed_runs(repo: str, token: str, branch: str, limit: int) -> list[WorkflowRun]:
    response = _github_request(
        "GET",
        _repo_api(repo, f"actions/runs?branch={branch}&status=completed&per_page={limit}"),
        token,
    )
    runs: list[WorkflowRun] = []
    for run in response.get("workflow_runs", []):
        if run.get("conclusion") in {"success", "neutral", "skipped"}:
            continue
        runs.append(
            WorkflowRun(
                id=run["id"],
                name=run.get("name") or "",
                status=run.get("status") or "unknown",
                conclusion=run.get("conclusion"),
                run_attempt=int(run.get("run_attempt") or 1),
                html_url=run.get("html_url") or "",
                head_branch=run.get("head_branch"),
                head_sha=run.get("head_sha"),
                event=run.get("event") or "unknown",
            )
        )
    return runs


def is_blocklisted(workflow_name: str) -> bool:
    normalized = workflow_name.lower()
    return any(keyword in normalized for keyword in BLOCKLISTED_KEYWORDS)


def has_transient_hint(conclusion: str | None, log_excerpt: str = "") -> bool:
    if conclusion in TRANSIENT_CONCLUSIONS:
        return True
    normalized = log_excerpt.lower()
    return any(hint in normalized for hint in TRANSIENT_LOG_HINTS)


def classify_run(run: WorkflowRun, log_excerpt: str = "") -> RerunDecision:
    allowlisted = run.name in ALLOWLISTED_WORKFLOWS
    blocked = is_blocklisted(run.name)
    transient = has_transient_hint(run.conclusion, log_excerpt)

    if blocked:
        return RerunDecision(run.id, run.name, "blocked", "workflow_blocklisted", transient, allowlisted, True, run.run_attempt)
    if not allowlisted:
        return RerunDecision(run.id, run.name, "blocked", "workflow_not_allowlisted", transient, allowlisted, False, run.run_attempt)
    if run.run_attempt >= MAX_RERUN_ATTEMPTS:
        return RerunDecision(run.id, run.name, "blocked", "max_rerun_attempts_reached", transient, allowlisted, False, run.run_attempt)
    if not transient:
        return RerunDecision(run.id, run.name, "blocked", "non_transient_failure", transient, allowlisted, False, run.run_attempt)
    return RerunDecision(run.id, run.name, "rerun", "transient_allowlisted_failure", transient, allowlisted, False, run.run_attempt)


def rerun_failed_jobs(repo: str, token: str, run_id: int) -> None:
    _github_request("POST", _repo_api(repo, f"actions/runs/{run_id}/rerun-failed-jobs"), token)


def build_report(decisions: list[RerunDecision], dry_run: bool) -> dict[str, Any]:
    rerun_count = sum(1 for decision in decisions if decision.rerun_executed)
    eligible_count = sum(1 for decision in decisions if decision.decision == "rerun")
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": dry_run,
        "max_rerun_attempts": MAX_RERUN_ATTEMPTS,
        "eligible_reruns": eligible_count,
        "rerun_executed": rerun_count,
        "blocked": sum(1 for decision in decisions if decision.decision == "blocked"),
        "decisions": [asdict(decision) for decision in decisions],
        "status": "rerun_executed" if rerun_count else "no_rerun_executed",
    }


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "auto-rerun-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Governed Auto-Rerun",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Status: `{report['status']}`",
        f"Dry run: `{report['dry_run']}`",
        "",
        "## Summary",
        "",
        f"- Eligible reruns: `{report['eligible_reruns']}`",
        f"- Reruns executed: `{report['rerun_executed']}`",
        f"- Blocked: `{report['blocked']}`",
        "",
        "## Decisions",
        "",
    ]
    for decision in report["decisions"]:
        lines.append(f"- `{decision['workflow_name']}`: `{decision['decision']}` — {decision['reason']}")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed auto-rerun for transient GitHub Actions failures.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output-dir", default="artifacts/auto-rerun")
    parser.add_argument("--execute", action="store_true", help="Execute eligible reruns. Default is audit-only dry run.")
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

    runs = fetch_recent_failed_runs(args.repo, token, args.branch, args.limit)
    decisions: list[RerunDecision] = []
    for run in runs:
        decision = classify_run(run)
        if args.execute and decision.decision == "rerun":
            rerun_failed_jobs(args.repo, token, run.id)
            decision = RerunDecision(**{**asdict(decision), "rerun_executed": True})
        decisions.append(decision)

    report = build_report(decisions, dry_run=not args.execute)
    write_artifacts(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
