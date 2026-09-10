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


DEFAULT_MIRROR_USERNAME = "reqsys-github-mirror"
FORBIDDEN_MIRROR_USER_IDS = {41625052}
MINIMUM_PUSH_ACCESS_LEVEL = 30


@dataclass(frozen=True)
class Config:
    api_url: str
    project_id: str
    token: str
    default_branch: str
    timeout_seconds: int
    dry_run: bool
    mirror_user_id: int | None
    mirror_username: str

    @classmethod
    def from_environment(cls, dry_run: bool) -> "Config":
        api_url = os.getenv("CI_API_V4_URL", "https://gitlab.com/api/v4").rstrip("/")
        project_id = os.getenv("CI_PROJECT_ID", "")
        token = os.getenv("GITLAB_PROVISIONING_TOKEN", "")
        default_branch = os.getenv("CI_DEFAULT_BRANCH", "main")
        timeout_raw = os.getenv("GITLAB_API_TIMEOUT_SECONDS", "20")
        mirror_user_raw = os.getenv("MIRROR_USER_ID", "").strip()
        mirror_username = os.getenv("MIRROR_USERNAME", DEFAULT_MIRROR_USERNAME).strip()

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
            if not mirror_username:
                raise ProvisioningError("MIRROR_USERNAME must not be empty")

        return cls(
            api_url=api_url,
            project_id=project_id,
            token=token,
            default_branch=default_branch,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            mirror_user_id=mirror_user_id,
            mirror_username=mirror_username,
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
            "User-Agent": "reqsys-gitlab-governance-provisioner/1.1",
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
        force_push = bool(current.get("allow_force_push", False))
        if not force_push:
            return {"control": "protected_branch", "status": "unchanged"}
        if config.dry_run:
            return {"control": "protected_branch", "status": "would_update"}
        client.request("PATCH", path, {"allow_force_push": False})
        return {"control": "protected_branch", "status": "updated"}

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

    if ("user_id", target_user_id) not in current_keys:
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
    """Grant only the configured mirror identity explicit push access to main.

    Existing allowances are preserved. The function fails closed when identity
    correlation is ambiguous, generic Developer push is present, the legacy
    mirror identity is still allowed, force-push is enabled, or the post-write
    read does not prove the requested state.
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
    actual_username = str(member.get("username") or "").strip()
    if actual_username != config.mirror_username:
        raise ProvisioningError(
            "Mirror identity mismatch: "
            f"user_id={target_user_id} username={actual_username!r}, "
            f"expected={config.mirror_username!r}"
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
            f"Protected branch {config.default_branch!r} must exist before granting mirror access"
        )

    current_entries = _push_allowances(current)
    current_keys = {key for entry in current_entries if (key := _allowance_key(entry))}

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
        raise ProvisioningError(
            "Generic Developer push allowance is present; refusing to broaden or mask access"
        )

    target_present = ("user_id", target_user_id) in current_keys
    force_push = bool(current.get("allow_force_push", False))

    if target_present and not force_push:
        return {
            "control": "mirror_push_allowance",
            "status": "unchanged",
            "user_id": target_user_id,
        }

    if config.dry_run:
        return {
            "control": "mirror_push_allowance",
            "status": "would_update",
            "user_id": target_user_id,
            "reason": (
                "disable_force_push" if target_present else "add_explicit_user_allowance"
            ),
        }

    payload: dict[str, Any] = {"allow_force_push": False}
    if not target_present:
        payload["allowed_to_push"] = [{"user_id": target_user_id}]
    client.request("PATCH", branch_path, payload)

    verify_status, verified = client.request("GET", branch_path)
    if verify_status != 200 or not isinstance(verified, dict):
        raise ProvisioningError("Could not re-read protected branch after mirror grant")

    valid, reason = _validate_mirror_branch_state(
        verified,
        target_user_id=target_user_id,
        previous_allowances=current_keys,
    )
    if not valid:
        raise ProvisioningError(
            f"Mirror push allowance postcondition failed: {reason}"
        )

    return {
        "control": "mirror_push_allowance",
        "status": "updated",
        "user_id": target_user_id,
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
        "schema_version": "1.1.0",
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
            ensure_mirror_push_allowance(client, config),
            ensure_approval_rule(client, config),
            ensure_variable(
                client,
                config,
                "GITLAB_GOVERNANCE_TOKEN",
                os.getenv("GITLAB_GOVERNANCE_TOKEN_SOURCE", ""),
            ),
            ensure_variable(
                client,
                config,
                "FLY_API_TOKEN",
                os.getenv("FLY_API_TOKEN_SOURCE", ""),
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
