#!/usr/bin/env python3
"""Post-merge runtime smoke sentinel.

Validates that the existing Runtime Production Smoke Governed workflow completed
successfully and published the expected artifact. The script is read-only against
GitHub APIs and writes only local evidence files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_WORKFLOW_NAME = "Runtime Production Smoke Governed"
EXPECTED_ARTIFACT_NAME = "runtime-production-smoke-governed"
BLOCKING_STATUSES = {"missing_event_payload", "wrong_workflow", "wrong_branch", "workflow_failed", "artifact_missing"}


@dataclass(frozen=True)
class SentinelResult:
    contract: str
    generated_at: str
    repository: str
    workflow_name: str | None
    branch: str | None
    run_id: int | None
    run_url: str | None
    conclusion: str | None
    expected_artifact: str
    artifacts: list[str]
    status: str
    blocking_issues: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _github_request(url: str, token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled GitHub API URL.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error: {exc}") from exc


def _artifact_names(payload: dict[str, Any]) -> list[str]:
    return sorted(str(item.get("name") or "") for item in payload.get("artifacts", []) if item.get("name"))


def fetch_artifacts(repo: str, run_id: int, token: str, request_json: Callable[[str, str], dict[str, Any]] = _github_request) -> list[str]:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    return _artifact_names(request_json(url, token))


def evaluate_event(
    event: dict[str, Any],
    *,
    repo: str,
    token: str | None,
    expected_workflow: str = EXPECTED_WORKFLOW_NAME,
    expected_artifact: str = EXPECTED_ARTIFACT_NAME,
    request_json: Callable[[str, str], dict[str, Any]] = _github_request,
) -> SentinelResult:
    run = event.get("workflow_run") or {}
    workflow_name = run.get("name")
    branch = run.get("head_branch")
    conclusion = run.get("conclusion")
    run_id = run.get("id")
    run_url = run.get("html_url")
    blocking: list[str] = []
    artifacts: list[str] = []

    if not run:
        blocking.append("missing_event_payload")
    if workflow_name != expected_workflow:
        blocking.append("wrong_workflow")
    if branch != "main":
        blocking.append("wrong_branch")
    if conclusion != "success":
        blocking.append("workflow_failed")
    if token and repo and run_id:
        artifacts = fetch_artifacts(repo, int(run_id), token, request_json=request_json)
    if expected_artifact not in artifacts:
        blocking.append("artifact_missing")

    status = "blocked" if any(item in BLOCKING_STATUSES for item in blocking) else "ready"
    return SentinelResult(
        contract="post-merge-runtime-smoke-sentinel",
        generated_at=_utc_now(),
        repository=repo,
        workflow_name=workflow_name,
        branch=branch,
        run_id=int(run_id) if run_id else None,
        run_url=run_url,
        conclusion=conclusion,
        expected_artifact=expected_artifact,
        artifacts=artifacts,
        status=status,
        blocking_issues=blocking,
    )


def render_summary(result: SentinelResult) -> str:
    lines = [
        "# Post-merge Runtime Smoke Sentinel",
        "",
        f"- Status: `{result.status}`",
        f"- Workflow: `{result.workflow_name}`",
        f"- Branch: `{result.branch}`",
        f"- Conclusion: `{result.conclusion}`",
        f"- Run ID: `{result.run_id}`",
        f"- Expected artifact: `{result.expected_artifact}`",
        f"- Artifacts: `{', '.join(result.artifacts) if result.artifacts else 'none'}`",
        "",
    ]
    if result.blocking_issues:
        lines.append("## Blocking issues")
        lines.extend(f"- `{item}`" for item in result.blocking_issues)
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate post-merge runtime smoke execution evidence.")
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--output-dir", default="artifacts/post-merge-runtime-smoke-sentinel")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not args.event_path:
        print("--event-path or GITHUB_EVENT_PATH is required", file=sys.stderr)
        return 2
    if not args.repo:
        print("--repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2
    event = _load_json(Path(args.event_path))
    result = evaluate_event(event, repo=args.repo, token=token)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "post-merge-runtime-smoke-sentinel.json").write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_summary(result), encoding="utf-8")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 1 if result.status == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
