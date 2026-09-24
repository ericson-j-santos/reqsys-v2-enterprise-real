#!/usr/bin/env python3
"""Materializa os required status checks canônicos no ruleset da main do ReqSys."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any

TARGET_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
TARGET_BRANCH = "main"
TARGET_RULESET_ID = 17998541
POLICY_PATH = Path("config/required-checks-inventory-policy.json")
REQUIRED_CHECKS = (
    "Required Fast Gate",
    "CI Router Result",
    "Sumario CI Enterprise Fast",
    "Validar artefatos de governança",
    "governance-validation",
    "Security Baseline",
    "Auditar proteção enterprise da branch",
    "Gate de merge governado",
)
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


def _ruleset() -> dict[str, Any]:
    return _gh_json(
        [
            "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{TARGET_REPOSITORY}/rulesets/{TARGET_RULESET_ID}",
        ],
        "target_ruleset_read_failed",
    )


def _policy_checks() -> tuple[str, ...]:
    try:
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtectionError("required_checks_policy_unreadable") from exc
    checks = tuple(str(item).strip() for item in data.get("recommended_required_contexts") or [] if str(item).strip())
    if checks != REQUIRED_CHECKS:
        raise ProtectionError("required_checks_policy_mismatch")
    return checks


def _status_rule(payload: dict[str, Any]) -> dict[str, Any] | None:
    matches = [
        rule for rule in payload.get("rules") or []
        if isinstance(rule, dict) and rule.get("type") == "required_status_checks"
    ]
    if len(matches) > 1:
        raise ProtectionError("multiple_required_status_check_rules")
    return matches[0] if matches else None


def _contexts(rule: dict[str, Any] | None) -> tuple[str, ...]:
    if not rule:
        return ()
    params = rule.get("parameters") or {}
    return tuple(
        str(item.get("context")).strip()
        for item in params.get("required_status_checks") or []
        if isinstance(item, dict) and item.get("context")
    )


def ruleset_compliant(payload: dict[str, Any]) -> bool:
    if payload.get("id") != TARGET_RULESET_ID:
        return False
    if payload.get("source") != TARGET_REPOSITORY or payload.get("target") != "branch":
        return False
    if payload.get("enforcement") != "active":
        return False
    if payload.get("bypass_actors") not in ([], None):
        return False
    ref_name = (payload.get("conditions") or {}).get("ref_name") or {}
    if "~DEFAULT_BRANCH" not in (ref_name.get("include") or []):
        return False
    rule_types = {
        str(rule.get("type"))
        for rule in payload.get("rules") or []
        if isinstance(rule, dict) and rule.get("type")
    }
    if not {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}.issubset(rule_types):
        return False
    rule = _status_rule(payload)
    params = (rule or {}).get("parameters") or {}
    return (
        tuple(_contexts(rule)) == REQUIRED_CHECKS
        and bool(params.get("strict_required_status_checks_policy"))
        and params.get("do_not_enforce_on_create") is False
    )


def build_update_payload(current: dict[str, Any]) -> dict[str, Any]:
    if current.get("id") != TARGET_RULESET_ID:
        raise ProtectionError("ruleset_id_mismatch")
    if current.get("source") != TARGET_REPOSITORY or current.get("target") != "branch":
        raise ProtectionError("ruleset_target_mismatch")
    if current.get("enforcement") != "active":
        raise ProtectionError("ruleset_not_active")
    if current.get("bypass_actors") not in ([], None):
        raise ProtectionError("ruleset_bypass_not_empty")
    ref_name = (current.get("conditions") or {}).get("ref_name") or {}
    if "~DEFAULT_BRANCH" not in (ref_name.get("include") or []):
        raise ProtectionError("ruleset_default_branch_not_targeted")

    preserved: list[dict[str, Any]] = []
    for rule in current.get("rules") or []:
        if not isinstance(rule, dict) or not rule.get("type"):
            raise ProtectionError("ruleset_rule_invalid")
        if rule.get("type") == "required_status_checks":
            continue
        preserved.append(copy.deepcopy(rule))

    preserved_types = {str(rule.get("type")) for rule in preserved}
    if not {"deletion", "non_fast_forward", "pull_request"}.issubset(preserved_types):
        raise ProtectionError("ruleset_existing_protections_missing")

    preserved.append({
        "type": "required_status_checks",
        "parameters": {
            "do_not_enforce_on_create": False,
            "required_status_checks": [{"context": context} for context in REQUIRED_CHECKS],
            "strict_required_status_checks_policy": True,
        },
    })
    return {
        "name": str(current.get("name") or "Ruleset"),
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": copy.deepcopy(current.get("bypass_actors") or []),
        "conditions": copy.deepcopy(current.get("conditions") or {}),
        "rules": preserved,
    }


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    target = path.resolve()
    repo_root = Path.cwd().resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise ProtectionError("evidence_path_outside_repo") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="reqsys-ruleset-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _ruleset_digest(payload: dict[str, Any]) -> str:
    relevant = {
        "name": payload.get("name"),
        "target": payload.get("target"),
        "enforcement": payload.get("enforcement"),
        "bypass_actors": payload.get("bypass_actors") or [],
        "conditions": payload.get("conditions") or {},
        "rules": payload.get("rules") or [],
    }
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _blocked(path: Path, reason: str, target_sha: str | None = None) -> int:
    _write_evidence(path, {
        "status": "BLOCKED",
        "reason": reason,
        "repository": TARGET_REPOSITORY,
        "branch": TARGET_BRANCH,
        "ruleset_id": TARGET_RULESET_ID,
        "target_sha": target_sha,
        "required_checks": list(REQUIRED_CHECKS),
        "host": socket.gethostname(),
        "independent_readback": False,
        "secret_value_exposed": False,
        "production_touched": False,
    })
    return 20


def main() -> int:
    parser = argparse.ArgumentParser(description="Materializa required checks no ruleset da main do ReqSys")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output

    target_sha: str | None = None
    try:
        if socket.gethostname().upper() != "DESKTOP-PDQK954":
            raise ProtectionError("unexpected_host")

        auth = _gh(["auth", "status", "--hostname", "github.com"])
        if auth.returncode != 0:
            raise ProtectionError("github_local_auth_unavailable")

        _policy_checks()
        before_branch = _branch()
        target_sha = str((before_branch.get("commit") or {}).get("sha") or "").strip().lower()
        if len(target_sha) != 40:
            raise ProtectionError("target_sha_invalid")

        before = _ruleset()
        previous_contexts = list(_contexts(_status_rule(before)))
        before_digest = _ruleset_digest(before)
        if ruleset_compliant(before):
            _write_evidence(output, {
                "status": "ALREADY_COMPLIANT",
                "repository": TARGET_REPOSITORY,
                "branch": TARGET_BRANCH,
                "ruleset_id": TARGET_RULESET_ID,
                "ruleset_active": True,
                "target_sha": target_sha,
                "required_checks": list(REQUIRED_CHECKS),
                "previous_required_checks": previous_contexts,
                "strict_required_status_checks": True,
                "bypass_actor_count": 0,
                "protected": True,
                "local_github_auth": True,
                "host": socket.gethostname(),
                "before_ruleset_sha256": before_digest,
                "after_ruleset_sha256": before_digest,
                "independent_readback": True,
                "secret_value_exposed": False,
                "production_touched": False,
            })
            return 0

        before_write_branch = _branch()
        current_sha = str((before_write_branch.get("commit") or {}).get("sha") or "").strip().lower()
        if current_sha != target_sha:
            raise ProtectionError("target_sha_changed_before_write")

        request_payload = build_update_payload(before)
        update = _gh(
            [
                "api",
                "--method", "PUT",
                "-H", "Accept: application/vnd.github+json",
                "-H", f"X-GitHub-Api-Version: {API_VERSION}",
                f"repos/{TARGET_REPOSITORY}/rulesets/{TARGET_RULESET_ID}",
                "--input", "-",
            ],
            stdin=json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")),
        )
        if update.returncode != 0:
            raise ProtectionError("ruleset_update_failed")

        after_branch = _branch()
        after_sha = str((after_branch.get("commit") or {}).get("sha") or "").strip().lower()
        if after_sha != target_sha:
            raise ProtectionError("target_sha_changed_after_write")
        if after_branch.get("protected") is not True:
            raise ProtectionError("branch_not_protected_after_write")

        after = _ruleset()
        if not ruleset_compliant(after):
            raise ProtectionError("ruleset_readback_mismatch")

        _write_evidence(output, {
            "status": "PROTECTION_APPLIED",
            "repository": TARGET_REPOSITORY,
            "branch": TARGET_BRANCH,
            "ruleset_id": TARGET_RULESET_ID,
            "ruleset_active": True,
            "target_sha": target_sha,
            "required_checks": list(REQUIRED_CHECKS),
            "previous_required_checks": previous_contexts,
            "strict_required_status_checks": True,
            "bypass_actor_count": len(after.get("bypass_actors") or []),
            "protected": True,
            "local_github_auth": True,
            "host": socket.gethostname(),
            "before_ruleset_sha256": before_digest,
            "after_ruleset_sha256": _ruleset_digest(after),
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
