from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

PR_REMEDIATION_TASK = "github.pr.remediate.v1"
FAILING_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure", "stale"}
TRANSIENT_CONCLUSIONS = {"timed_out", "cancelled"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

TRANSIENT_KEYWORDS = (
    "checkout", "setup", "install", "download", "upload", "cache", "network",
    "runner", "dependency", "rate limit", "timeout",
)
PROTECTED_KEYWORDS = (
    "security", "secret", "token", "permission", "deploy", "production",
    "migration", "branch protection", "policy",
)
DETERMINISTIC_KEYWORDS = (
    "test", "lint", "typecheck", "build", "guardrail", "contract", "schema",
    "compile", "format",
)


@dataclass(frozen=True)
class FailureSignal:
    run_id: int
    workflow: str
    conclusion: str
    run_attempt: int
    failed_steps: tuple[str, ...]
    kind: str


def validate_repository(value: str) -> str:
    repository = str(value or "").strip()
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository must use owner/name")
    return repository


def validate_sha(value: str) -> str:
    sha = str(value or "").strip().lower()
    if not SHA_RE.fullmatch(sha):
        raise ValueError("head_sha must be a lowercase 40-character SHA")
    return sha


def classify_failure(
    *,
    conclusion: str | None,
    workflow: str,
    failed_steps: Iterable[str],
) -> str:
    normalized = " | ".join([workflow, *failed_steps]).casefold()
    if any(token in normalized for token in PROTECTED_KEYWORDS):
        return "protected"
    if conclusion in TRANSIENT_CONCLUSIONS:
        return "transient"
    if any(token in normalized for token in DETERMINISTIC_KEYWORDS):
        return "deterministic"
    if any(token in normalized for token in TRANSIENT_KEYWORDS):
        return "transient"
    return "unknown"


def latest_failed_runs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = str(run.get("name") or "workflow-unknown")
        key = (str(run.get("updated_at") or run.get("created_at") or ""), int(run.get("id") or 0))
        existing = latest.get(name)
        if existing is None:
            latest[name] = run
            continue
        existing_key = (
            str(existing.get("updated_at") or existing.get("created_at") or ""),
            int(existing.get("id") or 0),
        )
        if key > existing_key:
            latest[name] = run
    return [
        run
        for run in latest.values()
        if str(run.get("status") or "") == "completed"
        and str(run.get("conclusion") or "") in FAILING_CONCLUSIONS | {"cancelled"}
    ]


def remediation_identity(
    repository: str,
    pr_number: int,
    head_sha: str,
    failures: Iterable[FailureSignal],
) -> str:
    repository = validate_repository(repository)
    head_sha = validate_sha(head_sha)
    normalized = [
        {
            "run_id": item.run_id,
            "workflow": item.workflow,
            "conclusion": item.conclusion,
            "run_attempt": item.run_attempt,
            "failed_steps": sorted(item.failed_steps),
            "kind": item.kind,
        }
        for item in failures
    ]
    normalized.sort(key=lambda item: (item["workflow"], item["run_id"]))
    raw = json.dumps(
        {
            "repository": repository,
            "pr_number": int(pr_number),
            "head_sha": head_sha,
            "failures": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_intake(
    *,
    repository: str,
    pr_number: int,
    head_sha: str,
    head_ref: str,
    base_ref: str,
    failures: list[FailureSignal],
) -> dict[str, Any]:
    repository = validate_repository(repository)
    head_sha = validate_sha(head_sha)
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
        raise ValueError("pr_number must be a positive integer")
    if not failures:
        raise ValueError("at least one failure is required")
    if any(item.kind == "protected" for item in failures):
        raise ValueError("protected failures cannot be auto-remediated")

    identity = remediation_identity(repository, pr_number, head_sha, failures)
    correlation_id = f"pr-remediate-{identity[:20]}"
    return {
        "event_id": f"github-pr-remediate-{identity[:32]}",
        "correlation_id": correlation_id,
        "idempotency_key": f"github-pr-remediate:{identity}",
        "task_type": PR_REMEDIATION_TASK,
        "risk": 2,
        "max_attempts": 3,
        "payload": {
            "worker_hint": "ci-remediator",
            "repository": repository,
            "pr_number": pr_number,
            "expected_head_sha": head_sha,
            "head_ref": str(head_ref or ""),
            "base_ref": str(base_ref or ""),
            "failure_fingerprint": identity,
            "failures": [
                {
                    "run_id": item.run_id,
                    "workflow": item.workflow,
                    "conclusion": item.conclusion,
                    "run_attempt": item.run_attempt,
                    "failed_steps": list(item.failed_steps),
                    "kind": item.kind,
                }
                for item in failures
            ],
            "constraints": {
                "same_pr": True,
                "expected_head_sha_required": True,
                "merge": False,
                "deploy": False,
                "force_push": False,
                "secrets": False,
            },
        },
    }
