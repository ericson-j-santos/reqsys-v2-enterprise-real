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
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_WORKFLOW_NAME = "Validação de Acessos Públicos — ReqSys"
EXPECTED_WORKFLOW_ID = 298568643
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
EXPECTED_ARTIFACT_NAME = "validacao-acessos-publicos"
EXPECTED_JOB_NAME = "Validar URLs públicas e gerar analítico"
REQUIRED_STEPS = frozenset({
    "Resolver locator DEV assinado",
    "Classificar defasagem do runtime DEV",
    "Validar runtime DEV real com política de SHA por escopo",
    "Validar acessos públicos",
    "Publicar relatório analítico",
})
_SHA = re.compile(r"^[0-9a-f]{40}$")


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
    source_sha: str | None
    main_sha: str | None
    source_event: str | None
    required_steps_verified: bool
    runtime_evidence_verified: bool
    runtime_observed_sha: str | None


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
        with urlopen(request, timeout=30) as response:  # nosec B310 - controlled GitHub API URL.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error: {exc}") from exc


def _artifact_names(payload: dict[str, Any]) -> list[str]:
    """Only current nonempty artifacts qualify; an expired ZIP is not evidence."""
    items = payload.get("artifacts")
    if not isinstance(items, list):
        return []
    return sorted(
        str(item["name"])
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item["name"]
        and item.get("expired") is False
        and type(item.get("size_in_bytes")) is int
        and item["size_in_bytes"] > 0
    )


def fetch_artifacts(repo: str, run_id: int, token: str, request_json: Callable[[str, str], dict[str, Any]] = _github_request) -> list[str]:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    return _artifact_names(request_json(url, token))


def _verified_job_steps(
    repo: str,
    run_id: int,
    token: str,
    request_json: Callable[[str, str], dict[str, Any]],
) -> bool:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    payload = request_json(url, token)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return False
    matching = [
        job for job in jobs
        if isinstance(job, dict) and job.get("name") == EXPECTED_JOB_NAME
    ]
    if len(matching) != 1:
        return False
    job = matching[0]
    if job.get("status") != "completed" or job.get("conclusion") != "success":
        return False
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    observed = {
        step.get("name")
        for step in steps
        if isinstance(step, dict)
        and step.get("status") == "completed"
        and step.get("conclusion") == "success"
    }
    return REQUIRED_STEPS <= observed


def _current_main_sha(
    repo: str,
    token: str,
    request_json: Callable[[str, str], dict[str, Any]],
) -> str | None:
    url = f"https://api.github.com/repos/{repo}/branches/main"
    payload = request_json(url, token)
    commit = payload.get("commit")
    value = commit.get("sha") if isinstance(commit, dict) else None
    return value if isinstance(value, str) and _SHA.fullmatch(value) else None


def _load_runtime_evidence(directory: Path) -> dict[str, Any] | None:
    """Read exactly one small, local artifact file downloaded from the upstream run."""
    if not directory.is_dir():
        return None
    resolved_root = directory.resolve()
    candidates = [
        item for item in directory.rglob("runtime-smoke.json")
        if item.is_file() and item.resolve().is_relative_to(resolved_root)
    ]
    if len(candidates) != 1:
        return None
    try:
        raw = candidates[0].read_bytes()
        if len(raw) > 65536:
            return None
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _verify_runtime_evidence(payload: dict[str, Any], expected_sha: str | None) -> tuple[bool, str | None]:
    """A successful upstream job does not replace independent runtime SHA checks."""
    if expected_sha is None or not isinstance(payload, dict):
        return False, None
    observed = payload.get("observed_sha")
    final = payload.get("final_observed_sha")
    if (
        payload.get("environment") != "dev"
        or payload.get("base_url_kind") != "signed_locator"
        or payload.get("expected_sha") != expected_sha
        or observed != expected_sha
        or final != expected_sha
        or payload.get("build_sha_matches_expected") is not True
    ):
        return False, observed if isinstance(observed, str) and _SHA.fullmatch(observed) else None
    for path in (
        "/api/health",
        "/api/runtime/health",
        "/api/runtime/readiness",
        "/api/runtime/build-info",
    ):
        item = payload.get(path)
        if not isinstance(item, dict) or item.get("http") != 200:
            return False, observed
    frontend = payload.get("frontend")
    if (
        not isinstance(frontend, dict)
        or frontend.get("mode") != "static_nginx"
        or frontend.get("http") != 200
        or frontend.get("vite_client_http") != 404
        or frontend.get("asset_http") != 200
    ):
        return False, observed
    return True, observed


def evaluate_event(
    event: dict[str, Any],
    *,
    repo: str,
    token: str | None,
    expected_workflow: str = EXPECTED_WORKFLOW_NAME,
    expected_artifact: str = EXPECTED_ARTIFACT_NAME,
    request_json: Callable[[str, str], dict[str, Any]] = _github_request,
    upstream_evidence: dict[str, Any] | None = None,
) -> SentinelResult:
    run = event.get("workflow_run") or {}
    if not isinstance(run, dict):
        run = {}
    workflow_name = run.get("name")
    branch = run.get("head_branch")
    conclusion = run.get("conclusion")
    source_event = run.get("event")
    source_sha = run.get("head_sha")
    run_id = run.get("id")
    run_url = run.get("html_url")
    blocking: list[str] = []
    artifacts: list[str] = []
    main_sha: str | None = None
    verified_steps = False
    runtime_evidence_verified = False
    runtime_observed_sha: str | None = None

    if not run:
        blocking.append("missing_event_payload")
    if repo != EXPECTED_REPOSITORY:
        blocking.append("repository_not_allowed")
    if workflow_name != expected_workflow or run.get("workflow_id") != EXPECTED_WORKFLOW_ID:
        blocking.append("wrong_workflow")
    if branch != "main":
        blocking.append("wrong_branch")
    if source_event != "push":
        blocking.append("wrong_source_event")
    if conclusion != "success":
        blocking.append("workflow_failed")
    if not isinstance(source_sha, str) or not _SHA.fullmatch(source_sha):
        blocking.append("source_sha_invalid")
        source_sha = None
    if type(run_id) is not int or run_id <= 0:
        blocking.append("run_id_invalid")

    if not token or repo != EXPECTED_REPOSITORY or type(run_id) is not int or run_id <= 0:
        blocking.append("github_provenance_unavailable")
    else:
        try:
            artifacts = fetch_artifacts(repo, run_id, token, request_json=request_json)
            verified_steps = _verified_job_steps(repo, run_id, token, request_json)
            main_sha = _current_main_sha(repo, token, request_json)
        except (RuntimeError, KeyError, TypeError, ValueError):
            blocking.append("github_read_unavailable")
    # GitHub preserves artifacts from previous attempts when a failed job is
    # re-run.  More than one current, non-empty artifact with the same name is
    # therefore valid provenance for the run; the downloaded runtime evidence
    # is still independently checked against the exact source SHA below.
    if expected_artifact not in artifacts:
        blocking.append("artifact_missing_or_invalid")
    if not verified_steps:
        blocking.append("required_steps_not_executed")
    if main_sha is None:
        blocking.append("main_sha_unverified")
    elif source_sha != main_sha:
        blocking.append("published_run_not_current_main_sha")

    if upstream_evidence is None:
        blocking.append("runtime_evidence_missing")
    else:
        runtime_evidence_verified, runtime_observed_sha = _verify_runtime_evidence(
            upstream_evidence, source_sha
        )
        if not runtime_evidence_verified:
            blocking.append("runtime_evidence_contract_failed")

    return SentinelResult(
        contract="post-merge-runtime-smoke-sentinel",
        generated_at=_utc_now(),
        repository=repo,
        workflow_name=str(workflow_name) if workflow_name is not None else None,
        branch=str(branch) if branch is not None else None,
        run_id=run_id if type(run_id) is int and run_id > 0 else None,
        run_url=str(run_url) if run_url is not None else None,
        conclusion=str(conclusion) if conclusion is not None else None,
        expected_artifact=expected_artifact,
        artifacts=artifacts,
        status="blocked" if blocking else "ready",
        blocking_issues=sorted(set(blocking)),
        source_sha=source_sha,
        main_sha=main_sha,
        source_event=str(source_event) if source_event is not None else None,
        required_steps_verified=verified_steps,
        runtime_evidence_verified=runtime_evidence_verified,
        runtime_observed_sha=runtime_observed_sha,
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
        f"- Source event: `{result.source_event}`",
        f"- Source SHA: `{result.source_sha}`",
        f"- Current main SHA: `{result.main_sha}`",
        f"- Required steps actually executed: `{result.required_steps_verified}`",
        f"- Runtime evidence verified: `{result.runtime_evidence_verified}`",
        f"- Observed runtime SHA: `{result.runtime_observed_sha}`",
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
    parser.add_argument("--upstream-evidence-dir", default="artifacts/upstream-public-dev")
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
    runtime_evidence = _load_runtime_evidence(Path(args.upstream_evidence_dir))
    result = evaluate_event(
        event, repo=args.repo, token=token, upstream_evidence=runtime_evidence
    )
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

