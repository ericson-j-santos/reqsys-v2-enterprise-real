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


@dataclass(frozen=True)
class Config:
    api_url: str
    project_id: str
    token: str
    default_branch: str
    timeout_seconds: int
    dry_run: bool

    @classmethod
    def from_environment(cls, dry_run: bool) -> "Config":
        api_url = os.getenv("CI_API_V4_URL", "https://gitlab.com/api/v4").rstrip("/")
        project_id = os.getenv("CI_PROJECT_ID", "")
        token = os.getenv("GITLAB_PROVISIONING_TOKEN", "")
        default_branch = os.getenv("CI_DEFAULT_BRANCH", "main")
        timeout_raw = os.getenv("GITLAB_API_TIMEOUT_SECONDS", "20")

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
        return cls(
            api_url=api_url,
            project_id=project_id,
            token=token,
            default_branch=default_branch,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
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
            "User-Agent": "reqsys-gitlab-governance-provisioner/1.0",
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
        "schema_version": "1.0.0",
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
