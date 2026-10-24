#!/usr/bin/env python3
"""Fail-closed eligibility check for the shared ReqSys DEV Windows runner pool.

The runner name and GitHub runner id are deliberately not part of this contract.
Identity comes from a local, non-secret manifest created during onboarding.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

INSTANCE_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,63}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class PreflightError(RuntimeError):
    pass


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PreflightError(code) from None
    if not isinstance(value, dict):
        raise PreflightError(code)
    return value


def _is_reparse(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except AttributeError:
        attrs = 0
    return path.is_symlink() or bool(
        attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _origin_repository(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if completed.returncode:
        raise PreflightError("repository_origin_unavailable")
    value = completed.stdout.strip().replace("\\", "/").removesuffix(".git")
    for prefix in ("https://github.com/", "ssh://git@github.com/", "git@github.com:"):
        if value.casefold().startswith(prefix.casefold()):
            candidate = value[len(prefix) :]
            if REPOSITORY.fullmatch(candidate):
                return candidate.casefold()
    raise PreflightError("repository_origin_not_allowlisted")


def validate(
    policy: dict[str, Any],
    manifest: dict[str, Any],
    *,
    profile: str,
    repo_paths: list[Path],
    os_name: str | None = None,
    which=shutil.which,
) -> dict[str, Any]:
    if policy.get("schema_version") != 1 or manifest.get("schema_version") != 1:
        raise PreflightError("schema_version_invalid")
    if (os_name or os.name) != "nt":
        raise PreflightError("windows_required")
    if manifest.get("pool") != policy.get("pool"):
        raise PreflightError("pool_mismatch")
    if manifest.get("environment") != "dev" or policy.get("environment") != "dev":
        raise PreflightError("environment_must_be_dev")
    if manifest.get("allowed_environments") != ["dev"]:
        raise PreflightError("environment_scope_invalid")

    instance_id = str(manifest.get("runner_instance_id", ""))
    if not INSTANCE_ID.fullmatch(instance_id) or instance_id.casefold().startswith("desktop-"):
        raise PreflightError("runner_instance_id_invalid")

    safeguards = manifest.get("safeguards")
    if safeguards != policy.get("required_safeguards"):
        raise PreflightError("safeguards_invalid")

    profiles = policy.get("profiles")
    selected = profiles.get(profile) if isinstance(profiles, dict) else None
    if not isinstance(selected, dict):
        raise PreflightError("profile_invalid")
    manifest_profile = str(manifest.get("profile", ""))
    provisioned = profiles.get(manifest_profile) if isinstance(profiles, dict) else None
    if not isinstance(provisioned, dict):
        raise PreflightError("manifest_profile_invalid")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list) or any(
        item not in capabilities for item in selected.get("capabilities", [])
    ):
        raise PreflightError("capability_missing")
    if sorted(capabilities) != sorted(provisioned.get("capabilities", [])):
        raise PreflightError("manifest_capabilities_invalid")
    expected_labels = [
        *policy.get("runner_labels", []),
        *provisioned.get("runner_labels", []),
    ]
    if manifest.get("runner_labels") != expected_labels:
        raise PreflightError("runner_labels_invalid")
    missing_tools = [tool for tool in selected.get("tools", []) if not which(tool)]
    if missing_tools:
        raise PreflightError("required_tool_missing")

    raw_root = str(manifest.get("runtime_root", "")).strip()
    runtime_root = Path(raw_root)
    if not raw_root or not runtime_root.is_absolute() or not runtime_root.is_dir():
        raise PreflightError("runtime_root_invalid")
    if _is_reparse(runtime_root):
        raise PreflightError("runtime_root_reparse_refused")
    lowered_parts = {part.casefold() for part in runtime_root.parts}
    if lowered_parts.intersection(policy.get("forbidden_environments", [])):
        raise PreflightError("non_dev_runtime_root_refused")

    allowed_repositories = {
        str(item).casefold() for item in policy.get("repositories", [])
    }
    observed_repositories: list[str] = []
    for repo in repo_paths:
        if not repo.is_dir() or _is_reparse(repo):
            raise PreflightError("repository_path_invalid")
        observed = _origin_repository(repo)
        if observed not in allowed_repositories:
            raise PreflightError("repository_not_allowlisted")
        observed_repositories.append(observed)

    return {
        "status": "eligible",
        "schema_version": 1,
        "pool": policy["pool"],
        "profile": profile,
        "provisioned_profile": manifest_profile,
        "environment": "dev",
        "runner_instance_id": instance_id,
        "runtime_root_valid": True,
        "repository_access_valid": True,
        "repositories_checked": sorted(set(observed_repositories)),
        "runner_labels": expected_labels,
        "safeguards_valid": True,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("config/reqsys-dev-runner-pool.json"))
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--profile", choices=("base", "runtime", "ollama"), default="base")
    parser.add_argument("--repository", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest or (
        Path(os.environ["REQSYS_DEV_RUNNER_MANIFEST"])
        if os.environ.get("REQSYS_DEV_RUNNER_MANIFEST")
        else None
    )
    try:
        if manifest_path is None:
            raise PreflightError("runner_manifest_required")
        result = validate(
            _load_json(args.policy, "policy_invalid"),
            _load_json(manifest_path, "runner_manifest_invalid"),
            profile=args.profile,
            repo_paths=args.repository or [Path.cwd()],
        )
        runtime_root = _load_json(manifest_path, "runner_manifest_invalid")["runtime_root"]
        if os.environ.get("GITHUB_ENV"):
            with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
                stream.write(f"REQSYS_DEV_RUNTIME_ROOT={runtime_root}\n")
                stream.write(f"REQSYS_DEV_RUNNER_INSTANCE_ID={result['runner_instance_id']}\n")
        payload = result
        exit_code = 0
    except PreflightError as exc:
        payload = {"status": "blocked", "reason_code": str(exc), "production_touched": False}
        exit_code = 1
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
