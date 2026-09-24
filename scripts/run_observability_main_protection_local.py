#!/usr/bin/env python3
"""Protege observability-platform/main usando apenas a autenticação GitHub local do Noteri."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any

TARGET_REPOSITORY = "ericson-j-santos/observability-platform"
TARGET_BRANCH = "main"
REQUIRED_CHECKS = ("test", "E2E Platform Evidence Gate / validate-evidence")
API_VERSION = "2026-03-10"


class ProtectionError(RuntimeError):
    pass


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def _gh(args: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("gh")
    if not executable:
        raise ProtectionError("github_cli_missing")
    return subprocess.run(
        [executable, *args],
        input=stdin,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_clean_env(),
        shell=False,
        check=False,
        timeout=30,
    )


def _gh_json(args: list[str], reason: str) -> dict[str, Any]:
    result = _gh(args)
    if result.returncode != 0:
        raise ProtectionError(reason)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProtectionError(f"{reason}_invalid_json") from exc
    if not isinstance(data, dict):
        raise ProtectionError(f"{reason}_invalid_payload")
    return data


def _branch() -> dict[str, Any]:
    return _gh_json(
        [
            "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{TARGET_REPOSITORY}/branches/{TARGET_BRANCH}",
        ],
        "target_branch_read_failed",
    )


def _check_runs(sha: str) -> dict[str, Any]:
    return _gh_json(
        [
            "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{TARGET_REPOSITORY}/commits/{sha}/check-runs?per_page=100",
        ],
        "target_checks_read_failed",
    )


def _protection() -> dict[str, Any]:
    return _gh_json(
        [
            "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{TARGET_REPOSITORY}/branches/{TARGET_BRANCH}/protection",
        ],
        "target_protection_read_failed",
    )


def protection_compliant(payload: dict[str, Any]) -> bool:
    required = payload.get("required_status_checks") or {}
    contexts = set(required.get("contexts") or [])
    checks = {
        str(item.get("context"))
        for item in (required.get("checks") or [])
        if isinstance(item, dict) and item.get("context")
    }
    enforce_admins = bool((payload.get("enforce_admins") or {}).get("enabled"))
    pr_required = payload.get("required_pull_request_reviews") is not None
    force_push = bool((payload.get("allow_force_pushes") or {}).get("enabled"))
    deletion = bool((payload.get("allow_deletions") or {}).get("enabled"))
    return (
        set(REQUIRED_CHECKS).issubset(contexts | checks)
        and bool(required.get("strict"))
        and enforce_admins
        and pr_required
        and not force_push
        and not deletion
    )


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    target = path.resolve()
    repo_root = Path.cwd().resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise ProtectionError("evidence_path_outside_repo") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="obs-protection-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _blocked(path: Path, reason: str, target_sha: str | None = None) -> int:
    _write_evidence(path, {
        "status": "BLOCKED",
        "reason": reason,
        "repository": TARGET_REPOSITORY,
        "branch": TARGET_BRANCH,
        "target_sha": target_sha,
        "required_checks": list(REQUIRED_CHECKS),
        "host": socket.gethostname(),
        "secret_value_exposed": False,
        "production_touched": False,
    })
    return 20


def main() -> int:
    parser = argparse.ArgumentParser(description="Protege observability-platform/main via auth local do Noteri")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output

    target_sha: str | None = None
    try:
        if socket.gethostname().casefold() != "noteri":
            raise ProtectionError("unexpected_host")

        auth = _gh(["auth", "status", "--hostname", "github.com"])
        if auth.returncode != 0:
            raise ProtectionError("github_local_auth_unavailable")

        before = _branch()
        target_sha = str((before.get("commit") or {}).get("sha") or "").strip().lower()
        if len(target_sha) != 40:
            raise ProtectionError("target_sha_invalid")

        checks = _check_runs(target_sha).get("check_runs") or []
        green_checks = {
            str(item.get("name"))
            for item in checks
            if isinstance(item, dict)
            and item.get("status") == "completed"
            and item.get("conclusion") == "success"
            and item.get("name")
        }
        if not set(REQUIRED_CHECKS).issubset(green_checks):
            raise ProtectionError("required_checks_not_green")

        if before.get("protected") is True:
            current_protection = _protection()
            if protection_compliant(current_protection):
                _write_evidence(output, {
                    "status": "ALREADY_COMPLIANT",
                    "repository": TARGET_REPOSITORY,
                    "branch": TARGET_BRANCH,
                    "target_sha": target_sha,
                    "required_checks": list(REQUIRED_CHECKS),
                    "protected": True,
                    "pull_request_required": True,
                    "enforce_admins": True,
                    "force_push_allowed": False,
                    "deletion_allowed": False,
                    "local_github_auth": True,
                    "host": socket.gethostname(),
                    "independent_readback": True,
                    "secret_value_exposed": False,
                    "production_touched": False,
                })
                return 0

        before_write = _branch()
        current_sha = str((before_write.get("commit") or {}).get("sha") or "").strip().lower()
        if current_sha != target_sha:
            raise ProtectionError("target_sha_changed_before_write")

        request_payload = {
            "required_status_checks": {"strict": True, "contexts": list(REQUIRED_CHECKS)},
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": False,
                "require_code_owner_reviews": False,
                "required_approving_review_count": 0,
                "require_last_push_approval": False,
            },
            "restrictions": None,
            "required_linear_history": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "block_creations": False,
            "required_conversation_resolution": False,
            "lock_branch": False,
            "allow_fork_syncing": False,
        }
        update = _gh(
            [
                "api",
                "--method", "PUT",
                "-H", "Accept: application/vnd.github+json",
                "-H", f"X-GitHub-Api-Version: {API_VERSION}",
                f"repos/{TARGET_REPOSITORY}/branches/{TARGET_BRANCH}/protection",
                "--input", "-",
            ],
            stdin=json.dumps(request_payload, separators=(",", ":")),
        )
        if update.returncode != 0:
            raise ProtectionError("branch_protection_update_failed")

        after_branch = _branch()
        after_sha = str((after_branch.get("commit") or {}).get("sha") or "").strip().lower()
        if after_sha != target_sha:
            raise ProtectionError("target_sha_changed_after_write")
        if after_branch.get("protected") is not True:
            raise ProtectionError("branch_not_protected_after_write")

        after_protection = _protection()
        if not protection_compliant(after_protection):
            raise ProtectionError("protection_readback_mismatch")

        _write_evidence(output, {
            "status": "PROTECTION_APPLIED",
            "repository": TARGET_REPOSITORY,
            "branch": TARGET_BRANCH,
            "target_sha": target_sha,
            "required_checks": list(REQUIRED_CHECKS),
            "protected": True,
            "pull_request_required": True,
            "enforce_admins": True,
            "force_push_allowed": False,
            "deletion_allowed": False,
            "local_github_auth": True,
            "host": socket.gethostname(),
            "independent_readback": True,
            "secret_value_exposed": False,
            "production_touched": False,
        })
        return 0
    except (ProtectionError, OSError, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, ProtectionError) else exc.__class__.__name__
        return _blocked(output, reason, target_sha)


if __name__ == "__main__":
    raise SystemExit(main())
