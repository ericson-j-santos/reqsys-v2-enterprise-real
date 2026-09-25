#!/usr/bin/env python3
"""Protege fecap-clipping-automation/main com ruleset fixo via autenticação GitHub local."""
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

TARGET_REPOSITORY = "ericson-j-santos/fecap-clipping-automation"
TARGET_BRANCH = "main"
RULESET_NAME = "main-protection"
EXPECTED_TARGET_SHA = "2b72e45012faeef84d1828faa97b7b8d4efd968f"
VALIDATED_SOURCE_SHA = "c756b4faa948a9a23f3faf09e2e5cf748914a5fd"
REQUIRED_CHECKS = ("tests",)
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


def _gh_json(args: list[str], reason: str) -> Any:
    result = _gh(args)
    if result.returncode != 0:
        raise ProtectionError(reason)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProtectionError(f"{reason}_invalid_json") from exc


def _api(path: str, reason: str) -> Any:
    return _gh_json(
        [
            "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            path,
        ],
        reason,
    )


def _branch() -> dict[str, Any]:
    data = _api(f"repos/{TARGET_REPOSITORY}/branches/{TARGET_BRANCH}", "target_branch_read_failed")
    if not isinstance(data, dict):
        raise ProtectionError("target_branch_payload_invalid")
    return data


def _commit(sha: str) -> dict[str, Any]:
    data = _api(f"repos/{TARGET_REPOSITORY}/commits/{sha}", "target_commit_read_failed")
    if not isinstance(data, dict):
        raise ProtectionError("target_commit_payload_invalid")
    return data


def _check_runs(sha: str) -> list[dict[str, Any]]:
    data = _api(f"repos/{TARGET_REPOSITORY}/commits/{sha}/check-runs?per_page=100", "target_checks_read_failed")
    if not isinstance(data, dict) or not isinstance(data.get("check_runs"), list):
        raise ProtectionError("target_checks_payload_invalid")
    return [item for item in data["check_runs"] if isinstance(item, dict)]


def _repository() -> dict[str, Any]:
    data = _api(f"repos/{TARGET_REPOSITORY}", "target_repository_read_failed")
    if not isinstance(data, dict):
        raise ProtectionError("target_repository_payload_invalid")
    return data


def _rulesets() -> list[dict[str, Any]]:
    data = _api(f"repos/{TARGET_REPOSITORY}/rulesets", "target_rulesets_read_failed")
    if not isinstance(data, list):
        raise ProtectionError("target_rulesets_payload_invalid")
    return [item for item in data if isinstance(item, dict)]


def _ruleset(ruleset_id: int) -> dict[str, Any]:
    data = _api(f"repos/{TARGET_REPOSITORY}/rulesets/{ruleset_id}", "target_ruleset_read_failed")
    if not isinstance(data, dict):
        raise ProtectionError("target_ruleset_payload_invalid")
    return data


def _ruleset_payload() -> dict[str, Any]:
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {
                "include": ["~DEFAULT_BRANCH"],
                "exclude": [],
            }
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {
                "type": "pull_request",
                "parameters": {
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_approving_review_count": 0,
                    "required_review_thread_resolution": False,
                    "automatic_copilot_code_review_enabled": False,
                    "allowed_merge_methods": ["merge", "squash", "rebase"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": check} for check in REQUIRED_CHECKS],
                    "strict_required_status_checks_policy": True,
                },
            },
        ],
    }


def ruleset_compliant(payload: dict[str, Any]) -> bool:
    if payload.get("name") != RULESET_NAME or payload.get("target") != "branch":
        return False
    if payload.get("enforcement") != "active":
        return False
    if payload.get("bypass_actors") not in ([], None):
        return False
    conditions = payload.get("conditions") or {}
    ref_name = conditions.get("ref_name") or {}
    if "~DEFAULT_BRANCH" not in (ref_name.get("include") or []):
        return False

    rules = payload.get("rules") or []
    typed = {str(rule.get("type")): rule for rule in rules if isinstance(rule, dict) and rule.get("type")}
    for required_type in ("deletion", "non_fast_forward", "required_linear_history", "pull_request", "required_status_checks"):
        if required_type not in typed:
            return False

    pr_params = typed["pull_request"].get("parameters") or {}
    if pr_params.get("dismiss_stale_reviews_on_push") is not True:
        return False
    if pr_params.get("required_approving_review_count") != 0:
        return False

    check_params = typed["required_status_checks"].get("parameters") or {}
    contexts = {
        str(item.get("context"))
        for item in (check_params.get("required_status_checks") or [])
        if isinstance(item, dict) and item.get("context")
    }
    if not set(REQUIRED_CHECKS).issubset(contexts):
        return False
    return check_params.get("strict_required_status_checks_policy") is True


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    target = path.resolve()
    repo_root = Path.cwd().resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise ProtectionError("evidence_path_outside_repo") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="fecap-main-protection-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _blocked(path: Path, reason: str, target_sha: str | None = None) -> int:
    _write_evidence(
        path,
        {
            "status": "BLOCKED",
            "reason": reason,
            "repository": TARGET_REPOSITORY,
            "branch": TARGET_BRANCH,
            "target_sha": target_sha,
            "expected_target_sha": EXPECTED_TARGET_SHA,
            "validated_source_sha": VALIDATED_SOURCE_SHA,
            "required_checks": list(REQUIRED_CHECKS),
            "host": socket.gethostname(),
            "secret_value_exposed": False,
            "production_touched": False,
        },
    )
    return 20


def _validate_preconditions() -> str:
    if socket.gethostname().upper() != "NOTERI":
        raise ProtectionError("unexpected_host")
    auth = _gh(["auth", "status", "--hostname", "github.com"])
    if auth.returncode != 0:
        raise ProtectionError("github_local_auth_unavailable")

    before = _branch()
    target_sha = str((before.get("commit") or {}).get("sha") or "").strip().lower()
    if target_sha != EXPECTED_TARGET_SHA:
        raise ProtectionError("target_sha_changed")

    commit = _commit(target_sha)
    parent_shas = {
        str(parent.get("sha") or "").strip().lower()
        for parent in (commit.get("parents") or [])
        if isinstance(parent, dict)
    }
    if VALIDATED_SOURCE_SHA not in parent_shas:
        raise ProtectionError("validated_source_not_parent_of_target")

    green_checks = {
        str(item.get("name"))
        for item in _check_runs(VALIDATED_SOURCE_SHA)
        if item.get("status") == "completed"
        and item.get("conclusion") == "success"
        and item.get("name")
    }
    if not set(REQUIRED_CHECKS).issubset(green_checks):
        raise ProtectionError("required_checks_not_green")
    return target_sha


def _upsert_ruleset() -> tuple[int, str]:
    matches = [
        item
        for item in _rulesets()
        if item.get("name") == RULESET_NAME and item.get("target") == "branch"
    ]
    if len(matches) > 1:
        raise ProtectionError("duplicate_ruleset_name")
    payload = _ruleset_payload()
    if matches:
        ruleset_id = int(matches[0]["id"])
        current = _ruleset(ruleset_id)
        if ruleset_compliant(current):
            return ruleset_id, "ALREADY_COMPLIANT"
        result = _gh(
            [
                "api",
                "--method", "PUT",
                "-H", "Accept: application/vnd.github+json",
                "-H", f"X-GitHub-Api-Version: {API_VERSION}",
                f"repos/{TARGET_REPOSITORY}/rulesets/{ruleset_id}",
                "--input", "-",
            ],
            stdin=json.dumps(payload, separators=(",", ":")),
        )
        if result.returncode != 0:
            raise ProtectionError("ruleset_update_failed")
        return ruleset_id, "PROTECTION_APPLIED"

    result = _gh(
        [
            "api",
            "--method", "POST",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{TARGET_REPOSITORY}/rulesets",
            "--input", "-",
        ],
        stdin=json.dumps(payload, separators=(",", ":")),
    )
    if result.returncode != 0:
        raise ProtectionError("ruleset_create_failed")
    try:
        created = json.loads(result.stdout)
        ruleset_id = int(created["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ProtectionError("ruleset_create_response_invalid") from exc
    return ruleset_id, "PROTECTION_APPLIED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Protege FECAP/main via ruleset e auth local governada")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    target_sha: str | None = None
    try:
        target_sha = _validate_preconditions()
        ruleset_id, status = _upsert_ruleset()

        after = _branch()
        after_sha = str((after.get("commit") or {}).get("sha") or "").strip().lower()
        if after_sha != target_sha:
            raise ProtectionError("target_sha_changed_after_write")
        if after.get("protected") is not True:
            raise ProtectionError("branch_not_protected_after_write")

        readback = _ruleset(ruleset_id)
        if not ruleset_compliant(readback):
            raise ProtectionError("ruleset_readback_mismatch")

        repo_after = _repository()
        if repo_after.get("default_branch") != TARGET_BRANCH:
            raise ProtectionError("default_branch_changed")

        _write_evidence(
            args.output,
            {
                "status": status,
                "repository": TARGET_REPOSITORY,
                "branch": TARGET_BRANCH,
                "target_sha": target_sha,
                "validated_source_sha": VALIDATED_SOURCE_SHA,
                "required_checks": list(REQUIRED_CHECKS),
                "ruleset_id": ruleset_id,
                "ruleset_name": RULESET_NAME,
                "ruleset_active": True,
                "strict_required_status_checks": True,
                "pull_request_required": True,
                "dismiss_stale_reviews_on_push": True,
                "required_linear_history": True,
                "bypass_actor_count": 0,
                "force_push_blocked": True,
                "deletion_blocked": True,
                "protected": True,
                "local_github_auth": True,
                "host": socket.gethostname(),
                "independent_readback": True,
                "secret_value_exposed": False,
                "production_touched": False,
            },
        )
        return 0
    except (ProtectionError, OSError, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, ProtectionError) else exc.__class__.__name__
        return _blocked(args.output, reason, target_sha)


if __name__ == "__main__":
    raise SystemExit(main())
