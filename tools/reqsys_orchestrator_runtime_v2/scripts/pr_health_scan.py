from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from orchestrator.pr_remediator import (
    FailureSignal,
    build_intake,
    classify_failure,
    latest_failed_runs,
)

API_VERSION = "2022-11-28"
DEFAULT_CONFIG = Path("config/pr-remediator-repositories.json")


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    body = None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "reqsys-pr-remediator"}
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-GitHub-Api-Version"] = API_VERSION
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            detail = {"message": raw[:500]}
        return exc.code, detail
    except URLError as exc:
        raise RuntimeError(f"request unavailable: {type(exc.reason).__name__}") from exc


def github_url(repository: str, path: str, **params: str | int) -> str:
    url = f"https://api.github.com/repos/{repository}/{path.lstrip('/')}"
    return f"{url}?{urlencode(params)}" if params else url


def github_get(repository: str, path: str, token: str, **params: str | int) -> Any:
    status, payload = request_json("GET", github_url(repository, path, **params), token=token)
    if status != 200:
        raise RuntimeError(f"GitHub GET {repository}/{path} failed HTTP {status}: {payload}")
    return payload


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported config schema_version")
    repositories = payload.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("config repositories must be a non-empty list")
    return payload


def list_open_prs(repository: str, token: str, limit: int) -> list[dict[str, Any]]:
    data = github_get(
        repository,
        "pulls",
        token,
        state="open",
        per_page=min(max(limit, 1), 100),
        sort="updated",
        direction="asc",
    )
    if not isinstance(data, list):
        raise RuntimeError("unexpected pull request response")
    return [item for item in data if isinstance(item, dict)]


def list_runs(repository: str, head_sha: str, token: str) -> list[dict[str, Any]]:
    data = github_get(repository, "actions/runs", token, head_sha=head_sha, per_page=100)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected workflow runs response")
    return [item for item in data.get("workflow_runs", []) if isinstance(item, dict)]


def failed_steps(repository: str, run_id: int, token: str) -> tuple[str, ...]:
    data = github_get(repository, f"actions/runs/{run_id}/jobs", token, per_page=100)
    if not isinstance(data, dict):
        return ()
    steps: list[str] = []
    for job in data.get("jobs", []):
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if isinstance(step, dict) and step.get("conclusion") in {
                "failure", "timed_out", "action_required", "cancelled"
            }:
                steps.append(str(step.get("name") or "step-unknown"))
    return tuple(steps)


def to_signal(repository: str, run: dict[str, Any], token: str) -> FailureSignal:
    run_id = int(run.get("id") or 0)
    workflow = str(run.get("name") or "workflow-unknown")
    conclusion = str(run.get("conclusion") or "unknown")
    steps = failed_steps(repository, run_id, token)
    return FailureSignal(
        run_id=run_id,
        workflow=workflow,
        conclusion=conclusion,
        run_attempt=int(run.get("run_attempt") or 1),
        failed_steps=steps,
        kind=classify_failure(conclusion=conclusion, workflow=workflow, failed_steps=steps),
    )


def submit_intake(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    status, response = request_json(
        "POST",
        endpoint.rstrip("/") + "/v1/intake",
        payload=payload,
        timeout=10,
    )
    if status not in (200, 201):
        raise RuntimeError(f"orchestrator intake failed HTTP {status}: {response}")
    if not isinstance(response, dict):
        raise RuntimeError("orchestrator returned a non-object response")
    return response


def analyze_pr(
    repository: str,
    pr: dict[str, Any],
    token: str,
    endpoint: str,
) -> dict[str, Any]:
    number = int(pr["number"])
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    head_sha = str(head.get("sha") or "").lower()
    head_repo = ((head.get("repo") or {}).get("full_name") or repository)
    if head_repo != repository:
        return {"pr_number": number, "status": "skipped", "reason": "fork_head"}

    failures = [to_signal(repository, run, token) for run in latest_failed_runs(list_runs(repository, head_sha, token))]
    protected = [item for item in failures if item.kind == "protected"]
    actionable = [item for item in failures if item.kind in {"deterministic", "unknown", "transient"}]

    result: dict[str, Any] = {
        "pr_number": number,
        "head_sha": head_sha,
        "failures": [
            {
                "run_id": item.run_id,
                "workflow": item.workflow,
                "conclusion": item.conclusion,
                "run_attempt": item.run_attempt,
                "kind": item.kind,
                "failed_steps": list(item.failed_steps),
            }
            for item in failures
        ],
    }
    if not failures:
        result["status"] = "healthy_or_pending"
        return result
    if protected:
        result["status"] = "blocked_protected_failure"
        return result
    if not actionable:
        result["status"] = "no_actionable_failure"
        return result

    intake = build_intake(
        repository=repository,
        pr_number=number,
        head_sha=head_sha,
        head_ref=str(head.get("ref") or ""),
        base_ref=str(base.get("ref") or ""),
        failures=actionable,
    )
    response = submit_intake(endpoint, intake)
    result.update(
        {
            "status": "queued",
            "correlation_id": intake["correlation_id"],
            "idempotency_key": intake["idempotency_key"],
            "work_item_id": (response.get("item") or {}).get("id"),
            "replayed": bool(response.get("replayed")),
            "dispatch": bool(response.get("dispatch")),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--endpoint", default=os.environ.get("ORCHESTRATOR_ENDPOINT", "http://127.0.0.1:8787"))
    args = parser.parse_args()

    token = os.environ.get("PR_REMEDIATOR_GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("PR_REMEDIATOR_GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2

    config = load_config(Path(args.config))
    limit = int(config.get("max_open_prs_per_repo", 100))
    summary: dict[str, Any] = {"repositories": [], "queued": 0, "errors": 0}
    for entry in config["repositories"]:
        if not isinstance(entry, dict) or not entry.get("enabled", False):
            continue
        repository = str(entry.get("name") or "")
        repo_result: dict[str, Any] = {"repository": repository, "prs": []}
        try:
            prs = list_open_prs(repository, token, limit)
            for pr in prs:
                item = analyze_pr(repository, pr, token, args.endpoint)
                repo_result["prs"].append(item)
                if item.get("status") == "queued":
                    summary["queued"] += 1
        except Exception as exc:
            repo_result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            summary["errors"] += 1
        summary["repositories"].append(repo_result)

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
