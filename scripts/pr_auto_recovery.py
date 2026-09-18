#!/usr/bin/env python3
"""Governed PR Auto Recovery diagnostics.

This script inspects open pull requests and produces evidence for recovery decisions.
It is intentionally read-only in v1: it does not create branches, open PRs, close PRs,
merge, approve, or mutate repository state.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CRITICAL_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "CI Enterprise Fast",
    "Governance Quality Gates",
    "Governança Padrão Ouro",
    "PR Conflict Guard",
    "PR Evidence Gate",
    "Branch Protection Audit",
    "PR CI Watch",
}

MUTATING_ACTIONS_DISABLED = True


@dataclass(frozen=True)
class WorkflowSignal:
    id: int
    name: str
    status: str | None
    conclusion: str | None
    url: str


@dataclass(frozen=True)
class PullRequestSignal:
    number: int
    title: str
    url: str
    draft: bool
    mergeable: bool | None
    state: str
    head_ref: str
    head_sha: str
    base_ref: str
    changed_files: int
    additions: int
    deletions: int
    workflow_signals: list[WorkflowSignal]
    recommended_action: str
    severity: str
    reasons: list[str]


def github_request(method: str, url: str, token: str) -> Any:
    request = Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
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


def api_url(repo: str, path: str, **params: str | int) -> str:
    url = f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"
    if params:
        return f"{url}?{urlencode(params)}"
    return url


def list_open_prs(repo: str, token: str, limit: int) -> list[dict[str, Any]]:
    payload = github_request("GET", api_url(repo, "pulls", state="open", per_page=limit, sort="updated", direction="desc"), token)
    return list(payload)


def get_pr(repo: str, token: str, number: int) -> dict[str, Any]:
    return github_request("GET", api_url(repo, f"pulls/{number}"), token)


def list_runs_for_sha(repo: str, token: str, sha: str) -> list[WorkflowSignal]:
    payload = github_request("GET", api_url(repo, "actions/runs", head_sha=sha, per_page=30), token)
    runs = []
    for run in payload.get("workflow_runs", []):
        name = run.get("name") or "unknown"
        if name not in CRITICAL_WORKFLOWS:
            continue
        runs.append(
            WorkflowSignal(
                id=int(run.get("id")),
                name=name,
                status=run.get("status"),
                conclusion=run.get("conclusion"),
                url=run.get("html_url") or "",
            )
        )
    return runs


def classify(pr: dict[str, Any], runs: list[WorkflowSignal]) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    failures = [run for run in runs if run.conclusion in {"failure", "cancelled", "timed_out", "action_required"}]
    pending = [run for run in runs if run.status in {"queued", "in_progress", "requested", "waiting"}]

    if pr.get("mergeable") is False:
        reasons.append("mergeable=false")
    if pr.get("draft"):
        reasons.append("draft=true")
    if failures:
        reasons.append("critical_workflow_failure=" + ",".join(sorted({run.name for run in failures})))
    if pending:
        reasons.append("critical_workflow_pending=" + ",".join(sorted({run.name for run in pending})))
    if not runs:
        reasons.append("no_critical_workflow_runs_found_for_head")

    if pr.get("mergeable") is False:
        return "P0", "CREATE_CLEAN_REPLACEMENT_PR_MANUALLY", reasons
    if failures:
        return "P0", "FIX_OR_RERUN_FAILED_CRITICAL_WORKFLOWS", reasons
    if pending:
        return "P1", "WAIT_AND_REVALIDATE_CI", reasons
    if pr.get("draft"):
        return "P1", "READY_FOR_REVIEW_AFTER_OWNER_VALIDATION", reasons
    return "P2", "MERGE_CANDIDATE_AFTER_REQUIRED_REVIEW", reasons


def build_signal(repo: str, token: str, pr_summary: dict[str, Any]) -> PullRequestSignal:
    pr = get_pr(repo, token, int(pr_summary["number"]))
    runs = list_runs_for_sha(repo, token, pr["head"]["sha"])
    severity, action, reasons = classify(pr, runs)
    return PullRequestSignal(
        number=int(pr["number"]),
        title=pr.get("title") or "",
        url=pr.get("html_url") or "",
        draft=bool(pr.get("draft")),
        mergeable=pr.get("mergeable"),
        state=pr.get("state") or "unknown",
        head_ref=pr["head"].get("ref") or "",
        head_sha=pr["head"].get("sha") or "",
        base_ref=pr["base"].get("ref") or "",
        changed_files=int(pr.get("changed_files") or 0),
        additions=int(pr.get("additions") or 0),
        deletions=int(pr.get("deletions") or 0),
        workflow_signals=runs,
        recommended_action=action,
        severity=severity,
        reasons=reasons,
    )


def write_report(signals: list[PullRequestSignal], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "generated_at": generated_at,
        "mode": "read-only-diagnostics",
        "mutating_actions_disabled": MUTATING_ACTIONS_DISABLED,
        "critical_workflows": sorted(CRITICAL_WORKFLOWS),
        "signals": [asdict(signal) for signal in signals],
    }
    (output_dir / "pr-auto-recovery.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# PR Auto Recovery Diagnostics",
        "",
        f"Generated at: `{generated_at}`",
        "Mode: `read-only-diagnostics`",
        "Mutating actions: `disabled`",
        "",
        "| PR | Severity | Mergeable | Draft | Recommended action | Reasons |",
        "|---:|---:|---:|---:|---|---|",
    ]
    for signal in signals:
        reasons = "; ".join(signal.reasons) or "none"
        lines.append(
            f"| [#{signal.number}]({signal.url}) | `{signal.severity}` | `{signal.mergeable}` | `{signal.draft}` | `{signal.recommended_action}` | {reasons} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate governed PR auto recovery diagnostics.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-dir", default="artifacts/pr-auto-recovery")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")

    summaries = list_open_prs(args.repo, token, args.limit)
    signals = [build_signal(args.repo, token, pr) for pr in summaries]
    signals.sort(key=lambda item: (item.severity, item.number))
    write_report(signals, Path(args.output_dir))
    print(json.dumps({"signals": len(signals), "mode": "read-only-diagnostics"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
