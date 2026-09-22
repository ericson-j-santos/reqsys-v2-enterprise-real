#!/usr/bin/env python3
"""Fail-fast guard para impedir CI caro sem manifesto Pre-PR do SHA exato."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_NAME = "Pre-PR Readiness Gate"


class AdmissionGuardError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def github_json(repository: str, path: str, token: str) -> dict[str, Any]:
    if not REPOSITORY_RE.fullmatch(repository):
        raise AdmissionGuardError("repository_invalid")
    if not token:
        raise AdmissionGuardError("github_token_missing")
    req = Request(
        f"https://api.github.com/repos/{repository}/{path.lstrip('/')}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        raise AdmissionGuardError(f"github_http_{exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise AdmissionGuardError("github_unreachable_or_invalid") from exc
    if not isinstance(payload, dict):
        raise AdmissionGuardError("github_payload_invalid")
    return payload


def successful_pre_pr_runs(runs: list[dict[str, Any]], head_sha: str) -> list[dict[str, Any]]:
    return sorted(
        [
            run for run in runs
            if isinstance(run, dict)
            and run.get("name") == WORKFLOW_NAME
            and str(run.get("head_sha") or "").lower() == head_sha
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ],
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )


def matching_artifact(artifacts: list[dict[str, Any]], head_sha: str) -> dict[str, Any] | None:
    expected = f"ci-admission-{head_sha}"
    for artifact in artifacts:
        if (
            isinstance(artifact, dict)
            and artifact.get("name") == expected
            and artifact.get("expired") is not True
        ):
            return artifact
    return None


def verify_admission(repository: str, head_sha: str, token: str) -> dict[str, Any]:
    sha = head_sha.strip().lower()
    if not SHA40.fullmatch(sha):
        raise AdmissionGuardError("head_sha_invalid")

    query = urlencode({"head_sha": sha, "per_page": 100})
    runs_payload = github_json(repository, f"actions/runs?{query}", token)
    runs = runs_payload.get("workflow_runs") if isinstance(runs_payload.get("workflow_runs"), list) else []
    candidates = successful_pre_pr_runs(runs, sha)
    if not candidates:
        raise AdmissionGuardError("pre_pr_success_missing_for_head_sha")

    for run in candidates:
        run_id = int(run.get("id") or 0)
        if run_id < 1:
            continue
        artifacts_payload = github_json(repository, f"actions/runs/{run_id}/artifacts?per_page=100", token)
        artifacts = artifacts_payload.get("artifacts") if isinstance(artifacts_payload.get("artifacts"), list) else []
        artifact = matching_artifact(artifacts, sha)
        if artifact:
            return {
                "schema_version": "1.0.0",
                "result": "ADMISSION_ACCEPTED",
                "generated_at_utc": utc_now(),
                "head_sha": sha,
                "workflow": WORKFLOW_NAME,
                "pre_pr_run_id": run_id,
                "artifact": {
                    "id": artifact.get("id"),
                    "name": artifact.get("name"),
                    "expired": artifact.get("expired"),
                },
            }
    raise AdmissionGuardError("admission_manifest_missing_for_head_sha")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida manifesto de admissão antes de CI caro.")
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--head-sha", default=os.getenv("GITHUB_SHA", ""))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.event_name != "pull_request":
        result = {
            "schema_version": "1.0.0",
            "result": "ADMISSION_NOT_REQUIRED",
            "generated_at_utc": utc_now(),
            "event_name": args.event_name,
            "head_sha": args.head_sha,
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0

    try:
        result = verify_admission(args.repository, args.head_sha, os.getenv("GITHUB_TOKEN", "").strip())
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0
    except AdmissionGuardError as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "ADMISSION_BLOCKED",
            "generated_at_utc": utc_now(),
            "head_sha": args.head_sha,
            "reason": str(exc),
        }
        args.output.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(blocked, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
