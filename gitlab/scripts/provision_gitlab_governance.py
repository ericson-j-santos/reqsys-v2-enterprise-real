#!/usr/bin/env python3
"""Provision ReqSys GitLab governance controls through the GitLab API.

The provisioner is idempotent, dependency-free and safe by default. It never
prints secret values and supports dry-run execution for change review.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProvisioningError(RuntimeError):
    """Raised when GitLab governance provisioning cannot continue safely."""


DEFAULT_MIRROR_NAME = "reqsys-github-mirror"
FORBIDDEN_MIRROR_USER_IDS = {41625052}
MINIMUM_PUSH_ACCESS_LEVEL = 30
MAINTAINER_ACCESS_LEVEL = 40


@dataclass(frozen=True)
class Config:
    api_url: str
    project_id: str
    token: str
    default_branch: str
    timeout_seconds: int
    dry_run: bool
    mirror_user_id: int | None
    mirror_name: str

    @classmethod
    def from_environment(cls, dry_run: bool) -> Config:
        api_url = os.getenv("CI_API_V4_URL", "https://gitlab.com/api/v4").rstrip("/")
        project_id = os.getenv("CI_PROJECT_ID", "")
        token = os.getenv("GITLAB_PROVISIONING_TOKEN", "")
        default_branch = os.getenv("CI_DEFAULT_BRANCH", "main")
        timeout_raw = os.getenv("GITLAB_API_TIMEOUT_SECONDS", "20")
        mirror_user_raw = os.getenv("MIRROR_USER_ID", "").strip()
        mirror_name = os.getenv("MIRROR_NAME", DEFAULT_MIRROR_NAME).strip()

        missing = [
            name
            for name, value in {
                "CI_PROJECT_ID": project_id,
                "GITLAB_PROVISIONING_TOKEN": token,
                "CI_DEFAULT_BRANCH": default_branch,
            }.items()
            if not value
        ]
        if missing:
            raise ProvisioningError(
                "Missing mandatory configuration: " + ", ".join(sorted(missing))
            )
        try:
            timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise ProvisioningError("GITLAB_API_TIMEOUT_SECONDS must be an integer") from exc
        if not 1 <= timeout_seconds <= 120:
            raise ProvisioningError(
                "GITLAB_API_TIMEOUT_SECONDS must be between 1 and 120"
            )

        mirror_user_id: int | None = None
        if mirror_user_raw:
            try:
                mirror_user_id = int(mirror_user_raw)
            except ValueError as exc:
                raise ProvisioningError("MIRROR_USER_ID must be an integer") from exc
            if mirror_user_id <= 0:
                raise ProvisioningError("MIRROR_USER_ID must be a positive integer")
            if mirror_user_id in FORBIDDEN_MIRROR_USER_IDS:
                raise ProvisioningError(
                    f"MIRROR_USER_ID {mirror_user_id} is explicitly forbidden"
                )
            if not mirror_name:
                raise ProvisioningError("MIRROR_NAME must not be empty")

        return cls(
            api_url=api_url,
            project_id=project_id,
            token=token,
            default_branch=default_branch,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            mirror_user_id=mirror_user_id,
            mirror_name=mirror_name,
        )


class GitLabClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.project = urllib.parse.quote(config.project_id, safe="")

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        allow_status: set[int] | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.config.api_url}/{path.lstrip('/')}"
        body = None
        headers = {
            "PRIVATE-TOKEN": self.config.token,
            "Accept": "application/json",
            "User-Agent": "reqsys-gitlab-governance-provisioner/1.2",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if allow_status and exc.code in allow_status:
                try:
                    return exc.code, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return exc.code, {"message": raw[:500]}
            raise ProvisioningError(
                f"GitLab API returned HTTP {exc.code} for {method} {url}: {raw[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProvisioningError(f"GitLab API unavailable for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ProvisioningError(f"GitLab API returned invalid JSON for {url}") from exc

    def project_path(self, suffix: str = "") -> str:
        return f"projects/{self.project}{suffix}"


def ensure_protected_branch(client: GitLabClient, config: Config) -> dict[str, Any]:
    encoded_branch = urllib.parse.quote(config.default_branch, safe="")
    path = client.project_path(f"/protected_branches/{encoded_branch}")
    status, current = client.request("GET", path, allow_status={404})
    desired = {
        "name": config.default_branch,
        "push_access_level": 40,
        "merge_access_level": 40,
        "allow_force_push": False,
    }
    if status == 200:
        if not isinstance(current, dict):
            raise ProvisioningError("Protected branch payload is invalid")

        push_entries = _push_allowances(current)
        merge_entries = _merge_allowances(current)
        push_developer = _entries_at_level(push_entries, MINIMUM_PUSH_ACCESS_LEVEL)
        merge_developer = _entries_at_level(merge_entries, MINIMUM_PUSH_ACCESS_LEVEL)

        if push_developer and not _has_access_level(push_entries, MAINTAINER_ACCESS_LEVEL):
            raise ProvisioningError(
                "Refusing to remove Developer push without Maintainer fallback"
            )
        if merge_developer and not _has_access_level(merge_entries, MAINTAINER_ACCESS_LEVEL):
            raise ProvisioningError(
                "Refusing to remove Developer merge without Maintainer fallback"
            )

        force_push = bool(current.get("allow_force_push", False))
        if not force_push and not push_developer and not merge_developer:
            return {"control": "protected_branch", "status": "unchanged"}

        reasons: list[str] = []
        if force_push:
            reasons.append("disable_force_push")
        if push_developer:
            reasons.append("remove_generic_developer_push")
        if merge_developer:
            reasons.append("remove_generic_developer_merge")

        if config.dry_run:
            return {
                "control": "protected_branch",
                "status": "would_update",
                "reason": ",".join(reasons),
                "developer_push_records": len(push_developer),
                "developer_merge_records": len(merge_developer),
            }

        payload: dict[str, Any] = {"allow_force_push": False}
        if push_developer:
            payload["allowed_to_push"] = _destroy_access_levels(push_developer)
        if merge_developer:
            payload["allowed_to_merge"] = _destroy_access_levels(merge_developer)
        client.request("PATCH", path, payload)

        verify_status, verified = client.request("GET", path)
        if verify_status != 200 or not isinstance(verified, dict):
            raise ProvisioningError("Could not re-read protected branch after hardening")
        if bool(verified.get("allow_force_push", False)):
            raise ProvisioningError("Protected branch postcondition failed: force_push_enabled")

        verified_push = _push_allowances(verified)
        verified_merge = _merge_allowances(verified)
        if _entries_at_level(verified_push, MINIMUM_PUSH_ACCESS_LEVEL):
            raise ProvisioningError(
                "Protected branch postcondition failed: generic_developer_push_present"
            )
        if _entries_at_level(verified_merge, MINIMUM_PUSH_ACCESS_LEVEL):
            raise ProvisioningError(
                "Protected branch postcondition failed: generic_developer_merge_present"
            )
        if push_developer and not _has_access_level(
            verified_push, MAINTAINER_ACCESS_LEVEL
        ):
            raise ProvisioningError(
                "Protected branch postcondition failed: maintainer_push_fallback_missing"
            )
        if merge_developer and not _has_access_level(
            verified_merge, MAINTAINER_ACCESS_LEVEL
        ):
            raise ProvisioningError(
                "Protected branch postcondition failed: maintainer_merge_fallback_missing"
            )

        return {
            "control": "protected_branch",
            "status": "updated",
            "verified": True,
            "removed_developer_push_records": len(push_developer),
            "removed_developer_merge_records": len(merge_developer),
        }

    if config.dry_run:
        return {"control": "protected_branch", "status": "would_create"}
    client.request("POST", client.project_path("/protected_branches"), desired)
    return {"control": "protected_branch", "status": "created"}


def _allowance_key(entry: dict[str, Any]) -> tuple[str, int] | None:
    """Return the logical identity of a protected-branch push allowance."""
    for field in (
        "user_id",
        "group_id",
        "deploy_key_id",
        "member_role_id",
        "access_level",
    ):
        value = entry.get(field)
        if isinstance(value, int):
            return field, value
    return None


def _push_allowances(branch: dict[str, Any]) -> list[dict[str, Any]]:
    entries = branch.get("push_access_levels") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def _merge_allowances(branch: dict[str, Any]) -> list[dict[str, Any]]:
    entries = branch.get("merge_access_levels") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def _entries_at_level(
    entries: list[dict[str, Any]], access_level: int
) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("access_level") == access_level]


def _has_access_level(entries: list[dict[str, Any]], access_level: int) -> bool:
    return any(entry.get("access_level") == access_level for entry in entries)


def _destroy_access_levels(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    removals: list[dict[str, Any]] = []
    for entry in entries:
        record_id = entry.get("id")
        access_level = entry.get("access_level")
        if not isinstance(record_id, int) or not isinstance(access_level, int):
            raise ProvisioningError(
                "Protected branch access-level record is missing numeric id/access_level"
            )
        removals.append(
            {"id": record_id, "access_level": access_level, "_destroy": True}
        )
    return removals


def _validate_mirror_branch_state(
    branch: dict[str, Any],
    *,
    target_user_id: int,
    previous_allowances: set[tuple[str, int]] | None = None,
) -> tuple[bool, str | None]:
    if bool(branch.get("allow_force_push", False)):
        return False, "force_push_enabled"

    current_entries = _push_allowances(branch)
    current_keys = {key for entry in current_entries if (key := _allowance_key(entry))}

    exact_user = ("user_id", target_user_id) in current_keys
    maintainer_role = ("access_level", MAINTAINER_ACCESS_LEVEL) in current_keys
    if not exact_user and not maintainer_role:
        return False, "target_user_missing"

    forbidden = sorted(
        user_id
        for user_id in FORBIDDEN_MIRROR_USER_IDS
        if ("user_id", user_id) in current_keys
    )
    if forbidden:
        return False, f"forbidden_user_present:{','.join(map(str, forbidden))}"

    if ("access_level", MINIMUM_PUSH_ACCESS_LEVEL) in current_keys:
        return False, "generic_developer_push_present"

    if previous_allowances is not None and not previous_allowances.issubset(current_keys):
        return False, "existing_allowance_removed"

    return True, None


def ensure_mirror_push_allowance(
    client: GitLabClient, config: Config
) -> dict[str, Any]:
    """Validate the configured mirror identity without self-elevating it.

    GitLab Free does not support selecting individual users in protected-branch
    push rules. An existing Maintainer role allowance is therefore accepted as a
    documented fallback, but never misreported as exact least-privilege access.
    """
    if config.mirror_user_id is None:
        return {
            "control": "mirror_push_allowance",
            "status": "skipped",
            "reason": "MIRROR_USER_ID not configured",
        }

    target_user_id = config.mirror_user_id
    member_path = client.project_path(f"/members/all/{target_user_id}")
    member_status, member = client.request("GET", member_path, allow_status={404})
    if member_status != 200 or not isinstance(member, dict):
        raise ProvisioningError(
            f"Mirror identity user_id={target_user_id} is not a readable project member"
        )
    actual_name = str(member.get("name") or "").strip()
    if actual_name != config.mirror_name:
        raise ProvisioningError(
            "Mirror identity mismatch: "
            f"user_id={target_user_id} name={actual_name!r}, "
            f"expected={config.mirror_name!r}"
        )
    if str(member.get("state") or "active") != "active":
        raise ProvisioningError(
            f"Mirror identity user_id={target_user_id} is not active"
        )
    access_level = member.get("access_level")
    if not isinstance(access_level, int) or access_level < MINIMUM_PUSH_ACCESS_LEVEL:
        raise ProvisioningError(
            f"Mirror identity user_id={target_user_id} has insufficient project access"
        )

    encoded_branch = urllib.parse.quote(config.default_branch, safe="")
    branch_path = client.project_path(f"/protected_branches/{encoded_branch}")
    branch_status, current = client.request("GET", branch_path, allow_status={404})
    if branch_status != 200 or not isinstance(current, dict):
        raise ProvisioningError(
            f"Protected branch {config.default_branch!r} must exist before validating mirror access"
        )

    current_entries = _push_allowances(current)
    current_keys = {
        key for entry in current_entries if (key := _allowance_key(entry))
    }

    forbidden = sorted(
        user_id
        for user_id in FORBIDDEN_MIRROR_USER_IDS
        if ("user_id", user_id) in current_keys
    )
    if forbidden:
        raise ProvisioningError(
            "Legacy mirror identity is still allowed to push: "
            + ", ".join(map(str, forbidden))
        )

    if ("access_level", MINIMUM_PUSH_ACCESS_LEVEL) in current_keys:
        if config.dry_run:
            return {
                "control": "mirror_push_allowance",
                "status": "would_validate_after_branch_hardening",
                "user_id": target_user_id,
                "reason": "generic_developer_push_planned_for_removal",
            }
        raise ProvisioningError(
            "Generic Developer push allowance remains after protected-branch hardening"
        )

    valid, reason = _validate_mirror_branch_state(
        current,
        target_user_id=target_user_id,
    )
    if not valid:
        if reason == "target_user_missing":
            return {
                "control": "mirror_push_allowance",
                "status": "manual_required",
                "reason": (
                    "No exact-user or Maintainer role push allowance exists; "
                    "automatic self-elevation is disabled"
                ),
                "user_id": target_user_id,
            }
        raise ProvisioningError(
            f"Mirror push allowance validation failed: {reason}"
        )

    exact_user = ("user_id", target_user_id) in current_keys
    grant_mode = "exact_user" if exact_user else "maintainer_role_fallback"
    return {
        "control": "mirror_push_allowance",
        "status": "unchanged",
        "user_id": target_user_id,
        "grant_mode": grant_mode,
        "least_privilege_exact_identity": exact_user,
        "verified": True,
    }


def ensure_project_merge_policy(
    client: GitLabClient, config: Config
) -> dict[str, Any]:
    """Require successful pipelines and reject skipped pipelines for merge."""
    path = client.project_path()
    status, current = client.request("GET", path)
    if status != 200 or not isinstance(current, dict):
        raise ProvisioningError("Could not read project merge policy")

    pipeline_required = current.get("only_allow_merge_if_pipeline_succeeds") is True
    skipped_rejected = current.get("allow_merge_on_skipped_pipeline") is False
    if pipeline_required and skipped_rejected:
        return {"control": "project_merge_policy", "status": "unchanged"}

    desired = {
        "only_allow_merge_if_pipeline_succeeds": True,
        "allow_merge_on_skipped_pipeline": False,
    }
    if config.dry_run:
        return {
            "control": "project_merge_policy",
            "status": "would_update",
            "reason": "require_success_and_reject_skipped_pipeline",
        }

    client.request("PUT", path, desired)
    verify_status, verified = client.request("GET", path)
    if verify_status != 200 or not isinstance(verified, dict):
        raise ProvisioningError("Could not re-read project merge policy")
    if verified.get("only_allow_merge_if_pipeline_succeeds") is not True:
        raise ProvisioningError(
            "Project merge policy postcondition failed: pipeline_success_not_required"
        )
    if verified.get("allow_merge_on_skipped_pipeline") is not False:
        raise ProvisioningError(
            "Project merge policy postcondition failed: skipped_pipeline_still_allowed"
        )
    return {
        "control": "project_merge_policy",
        "status": "updated",
        "verified": True,
    }


def ensure_approval_rule(client: GitLabClient, config: Config) -> dict[str, Any]:
    path = client.project_path("/approval_rules")
    status, rules = client.request("GET", path, allow_status={403, 404})
    if status in {403, 404}:
        return {
            "control": "approval_rule",
            "status": "manual_required",
            "reason": "approval rules API unavailable for this project or GitLab plan",
        }
    existing = next(
        (rule for rule in rules if str(rule.get("name")) == "ReqSys Default Approval"),
        None,
    )
    if existing and int(existing.get("approvals_required", 0)) >= 1:
        return {"control": "approval_rule", "status": "unchanged"}
    if config.dry_run:
        return {
            "control": "approval_rule",
            "status": "would_update" if existing else "would_create",
        }
    payload = {"name": "ReqSys Default Approval", "approvals_required": 1}
    if existing:
        client.request("PUT", f"{path}/{existing['id']}", payload)
        return {"control": "approval_rule", "status": "updated"}
    client.request("POST", path, payload)
    return {"control": "approval_rule", "status": "created"}


def ensure_variable(
    client: GitLabClient,
    config: Config,
    key: str,
    value: str,
    environment_scope: str = "*",
) -> dict[str, Any]:
    if not value:
        return {
            "control": f"variable:{key}",
            "status": "manual_required",
            "reason": f"source value for {key} was not supplied",
        }
    encoded_key = urllib.parse.quote(key, safe="")
    base_path = client.project_path("/variables")
    status, _ = client.request("GET", f"{base_path}/{encoded_key}", allow_status={404})
    payload = {
        "key": key,
        "value": value,
        "variable_type": "env_var",
        "protected": True,
        "masked": True,
        "raw": True,
        "environment_scope": environment_scope,
    }
    if config.dry_run:
        return {
            "control": f"variable:{key}",
            "status": "would_update" if status == 200 else "would_create",
        }
    if status == 200:
        client.request("PUT", f"{base_path}/{encoded_key}", payload)
        return {"control": f"variable:{key}", "status": "updated"}
    client.request("POST", base_path, payload)
    return {"control": f"variable:{key}", "status": "created"}


def build_report(config: Config, actions: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = [item for item in actions if item["status"] == "manual_required"]
    return {
        "schema_version": "1.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": config.project_id,
        "default_branch": config.default_branch,
        "dry_run": config.dry_run,
        "status": "manual_required" if blocking else "provisioned",
        "actions": actions,
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "gitlab-governance-provisioning.json"
    md_path = output_dir / "gitlab-governance-provisioning.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# GitLab Governance Provisioning",
        "",
        f"Generated at: {report['generated_at']}",
        f"Status: **{report['status']}**",
        f"Dry run: `{report['dry_run']}`",
        "",
        "| Control | Result | Detail |",
        "|---|---|---|",
    ]
    for action in report["actions"]:
        detail = str(action.get("reason", "-")).replace("|", "\\|")
        lines.append(f"| `{action['control']}` | `{action['status']}` | {detail} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    parser.add_argument("--output-dir", default="audit")
    args = parser.parse_args()
    try:
        config = Config.from_environment(dry_run=not args.apply)
        client = GitLabClient(config)
        actions = [
            ensure_protected_branch(client, config),
            ensure_project_merge_policy(client, config),
            ensure_mirror_push_allowance(client, config),
            ensure_approval_rule(client, config),
            ensure_variable(
                client,
                config,
                "GITLAB_GOVERNANCE_TOKEN",
                os.getenv("GITLAB_GOVERNANCE_TOKEN_SOURCE", ""),
            ),
        ]
        report = build_report(config, actions)
        write_report(report, Path(args.output_dir))
        print(json.dumps({"status": report["status"], "dry_run": report["dry_run"]}))
        return 0
    except ProvisioningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
