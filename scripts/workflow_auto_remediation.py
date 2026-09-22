#!/usr/bin/env python3
"""Safe Workflow Auto Remediation for ReqSys.

Finds recent failed GitHub Actions workflow runs and, when explicitly enabled,
reruns failed jobs for allowlisted workflows only.
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
    "Main Smoke CI",
    "Main Operational Health",
    "Workflow Command Center",
    "Fast CI - Operational Guardrails",
    "PR Conflict Guard",
    "Branch Protection Audit",
    "Governance Quality Gates",
    "CI Enterprise Fast",
}

BLOCKED_WORKFLOWS = {
    "Deploy",
    "Production",
    "Fly Deploy",
    "Release",
}

RERUNABLE_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}


@dataclass(frozen=True)
class RemediationCandidate:
    id: int
    name: str
    conclusion: str | None
    event: str
    branch: str | None
    commit_sha: str | None
    url: str
    rerun_allowed: bool
    blocked_reason: str | None


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


def _is_blocked(name: str) -> str | None:
    lowered = name.lower()
    for blocked in BLOCKED_WORKFLOWS:
        if blocked.lower() in lowered:
            return f"workflow name matches blocked token: {blocked}"
    return None


def fetch_failed_runs(repo: str, token: str, branch: str, limit: int) -> list[RemediationCandidate]:
    response = _github_request(
        "GET",
        _repo_api(repo, f"actions/runs?branch={branch}&status=completed&per_page={limit}"),
        token,
    )
    candidates: list[RemediationCandidate] = []
    for run in response.get("workflow_runs", []):
        conclusion = run.get("conclusion")
        if conclusion not in RERUNABLE_CONCLUSIONS:
            continue
        name = run.get("name") or ""
        blocked_reason = _is_blocked(name)
        rerun_allowed = name in ALLOWLISTED_WORKFLOWS and blocked_reason is None
        if not rerun_allowed and blocked_reason is None:
            blocked_reason = "workflow is not in remediation allowlist"
        candidates.append(
            RemediationCandidate(
                id=run["id"],
                name=name,
                conclusion=conclusion,
                event=run.get("event") or "unknown",
                branch=run.get("head_branch"),
                commit_sha=run.get("head_sha"),
                url=run.get("html_url") or "",
                rerun_allowed=rerun_allowed,
                blocked_reason=blocked_reason,
            )
        )
    return candidates


def rerun_failed_jobs(repo: str, token: str, run_id: int) -> None:
    _github_request("POST", _repo_api(repo, f"actions/runs/{run_id}/rerun-failed-jobs"), token)


def build_report(candidates: list[RemediationCandidate], executed: bool, remediated: list[int]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "execute" if executed else "dry-run",
        "allowlisted_workflows": sorted(ALLOWLISTED_WORKFLOWS),
        "blocked_tokens": sorted(BLOCKED_WORKFLOWS),
        "candidates": [asdict(candidate) for candidate in candidates],
        "remediated_run_ids": remediated,
        "blocked_candidates": [asdict(candidate) for candidate in candidates if not candidate.rerun_allowed],
        "status": "remediated" if remediated else "no-remediation-executed",
    }


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "workflow-auto-remediation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Workflow Auto Remediation",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Mode: `{report['mode']}`",
        f"Status: `{report['status']}`",
        "",
        "## Summary",
        "",
        f"- Candidates: `{len(report['candidates'])}`",
        f"- Remediated: `{len(report['remediated_run_ids'])}`",
        f"- Blocked: `{len(report['blocked_candidates'])}`",
        "",
    ]
    if report["candidates"]:
        lines.extend(["## Candidates", ""])
        for candidate in report["candidates"]:
            state = "allowed" if candidate["rerun_allowed"] else f"blocked: {candidate['blocked_reason']}"
            lines.append(f"- [{candidate['name']}]({candidate['url']}) — `{candidate['conclusion']}` — {state}")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely rerun failed jobs for allowlisted workflows.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--execute", action="store_true", help="Actually rerun failed jobs. Default is dry-run.")
    parser.add_argument("--max-reruns", type=int, default=3)
    parser.add_argument("--output-dir", default="artifacts/workflow-auto-remediation")
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

    candidates = fetch_failed_runs(args.repo, token, args.branch, args.limit)
    remediated: list[int] = []
    if args.execute:
        for candidate in candidates:
            if len(remediated) >= args.max_reruns:
                break
            if candidate.rerun_allowed:
                rerun_failed_jobs(args.repo, token, candidate.id)
                remediated.append(candidate.id)

    report = build_report(candidates, args.execute, remediated)
    write_artifacts(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
