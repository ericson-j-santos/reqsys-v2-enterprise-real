#!/usr/bin/env python3
"""Reconcilia o runtime Teams DEV persistente do PC24x7 com um SHA governado."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PureWindowsPath
from typing import Any


def _load_provision_module():
    module_path = Path(__file__).resolve().with_name("provision_pc24x7_teams_bot_runtime.py")
    spec = importlib.util.spec_from_file_location("reqsys_pc24x7_teams_provision", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("provision_module_loader_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provision = _load_provision_module()

CONFIRMATION = "RECONCILE-PC24X7-TEAMS-DEV"
EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_PROJECT = "wt-pc24x7-piloto"
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEV_API_PORT = "8210"
ADMIN_OVERRIDE_NAME = "docker-compose.admin-dev.override.yml"
PUBLIC_OVERRIDE_NAME = "docker-compose.pc24x7-public-dev.yml"
PUBLIC_RUNTIME_PROFILE = "pc24x7-public-dev"
TEAMS_OVERRIDE_REL = Path("config/pc24x7-teams-bot-runtime.override.yml")


class ReconcileError(RuntimeError):
    def __init__(self, message: str, *, mutation_state: str = "not_attempted") -> None:
        super().__init__(message)
        self.mutation_state = mutation_state
        self.mutation_performed = mutation_state != "not_attempted"


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        found = shutil.which(candidate)
        if found:
            return found
    raise ReconcileError(f"tool_missing:{name}")


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 180,
    sensitive: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise ReconcileError("command_timeout") from None
    except OSError:
        raise ReconcileError("command_spawn_failed") from None
    if check and result.returncode != 0:
        code = "sensitive_command_failed" if sensitive else "command_failed"
        raise ReconcileError(code)
    return result


def _windows_path(raw: str) -> Path:
    value = raw.strip()
    lowered = value.lower()
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if lowered.startswith(prefix):
            tail = value[len(prefix):]
            parts = tail.split("/", 1)
            if len(parts) == 2 and len(parts[0]) == 1:
                return Path(f"{parts[0].upper()}:/{parts[1]}")
    return Path(value)


def _require_host() -> None:
    if os.name != "nt":
        raise ReconcileError("windows_required")
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise ReconcileError("host_not_allowed")


def _inspect_value(container_id: str, template: str, cwd: Path) -> str:
    return _run(
        [_tool("docker"), "inspect", "--format", template, container_id],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()


def _has_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ReconcileError("public_override_metadata_unreadable") from exc
    attrs = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _validate_public_override(
    runtime_root: Path,
    candidate: Path,
    expected_sha: str | None = None,
) -> Path:
    raw = str(candidate)
    if (
        not raw
        or raw.startswith(("\\\\", "//"))
        or re.match(r"^[A-Za-z]:[^\\/]", raw)
        or re.search(r"[\\/]{2,}", raw)
        or ".." in PureWindowsPath(raw).parts
        or ":" in raw[2:]
    ):
        raise ReconcileError("public_override_path_unsafe")
    root_abs = Path(os.path.abspath(runtime_root))
    candidate_abs = Path(os.path.abspath(candidate))
    expected_abs = root_abs / PUBLIC_OVERRIDE_NAME
    if os.path.normcase(str(candidate_abs)) != os.path.normcase(str(expected_abs)):
        raise ReconcileError("public_override_not_canonical")
    for target in (root_abs, candidate_abs):
        chain = [target, *target.parents]
        for cursor in reversed(chain):
            if not cursor.exists():
                raise ReconcileError("public_override_metadata_unreadable")
            if _has_reparse_point(cursor):
                raise ReconcileError("public_override_reparse_blocked")
    resolved_root = root_abs.resolve(strict=True)
    resolved = candidate_abs.resolve(strict=True)
    if resolved.parent != resolved_root:
        raise ReconcileError("public_override_outside_runtime")
    head = expected_sha or _git(runtime_root, "rev-parse", "HEAD").stdout.strip()
    tracked = _git(runtime_root, "rev-parse", f"{head}:{PUBLIC_OVERRIDE_NAME}", check=False)
    # Compare the working-tree file with the committed blob using the same
    # clean filters Git applies for this repository path. On Windows,
    # --no-filters hashes CRLF bytes directly and can report a false mismatch
    # even when `git status` considers the file clean.
    observed = _git(
        runtime_root,
        "hash-object",
        "--path",
        PUBLIC_OVERRIDE_NAME,
        str(candidate_abs),
        check=False,
    )
    if (
        tracked.returncode != 0
        or observed.returncode != 0
        or not re.fullmatch(r"[0-9a-f]{40}", tracked.stdout.strip())
        or tracked.stdout.strip() != observed.stdout.strip()
    ):
        raise ReconcileError("public_override_head_mismatch")
    return resolved


def _require_local_docker(cwd: Path) -> None:
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise ReconcileError("docker_environment_override_blocked")
    raw = _run(
        [_tool("docker"), "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()
    try:
        endpoint = str(json.loads(raw)).lower()
    except json.JSONDecodeError as exc:
        raise ReconcileError("docker_context_invalid") from exc
    if endpoint != "npipe:////./pipe/docker_engine":
        raise ReconcileError("docker_remote_context_blocked")


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(Path(os.path.abspath(left)))) == os.path.normcase(
        str(Path(os.path.abspath(right)))
    )


def _compose_paths(raw: str, runtime_root: Path) -> list[Path]:
    paths: list[Path] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        path = _windows_path(value)
        if not path.is_absolute():
            path = runtime_root / path
        paths.append(path)
    return paths


def _recover_public_override_from_siblings(
    runtime_root: Path,
    admin_override: Path,
    cwd: Path,
) -> Path:
    """Prove the public DEV identity from unchanged sibling services.

    A narrowly scoped recovery is allowed only when both frontend and nginx still
    carry the same canonical, last-applied public overlay and the same external
    admin override as the API. This repairs the known API-only Compose drift
    without accepting a project name or port binding as sufficient identity.
    """
    proven: list[Path] = []
    for service in ("frontend", "nginx"):
        result = _run(
            [
                _tool("docker"),
                "ps",
                "--filter", f"label=com.docker.compose.project={EXPECTED_PROJECT}",
                "--filter", f"label=com.docker.compose.service={service}",
                "--format", "{{.ID}}",
            ],
            cwd=cwd,
            timeout=60,
        )
        ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(ids) != 1:
            raise ReconcileError("public_dev_runtime_identity_not_proven")

        labels = {
            name: _inspect_value(ids[0], f'{{{{index .Config.Labels "{name}"}}}}', cwd)
            for name in (
                "com.docker.compose.project",
                "com.docker.compose.service",
                "com.docker.compose.project.working_dir",
                "com.docker.compose.project.config_files",
            )
        }
        sibling_root = _windows_path(
            labels["com.docker.compose.project.working_dir"].strip()
        )
        if (
            labels["com.docker.compose.project"].strip() != EXPECTED_PROJECT
            or labels["com.docker.compose.service"].strip() != service
            or not _same_path(sibling_root, runtime_root)
        ):
            raise ReconcileError("public_dev_runtime_identity_not_proven")

        paths = _compose_paths(
            labels["com.docker.compose.project.config_files"], runtime_root
        )
        admins = [
            path.resolve()
            for path in paths
            if path.name.casefold() == ADMIN_OVERRIDE_NAME.casefold() and path.is_file()
        ]
        publics = [
            path
            for path in paths
            if path.name.casefold() == PUBLIC_OVERRIDE_NAME.casefold() and path.is_file()
        ]
        if (
            len(admins) != 1
            or not _same_path(admins[0], admin_override)
            or len(publics) != 1
            or not paths
            or not _same_path(paths[-1], publics[0])
        ):
            raise ReconcileError("public_dev_runtime_identity_not_proven")
        proven.append(_validate_public_override(runtime_root, publics[0]))

    if len(proven) != 2 or not _same_path(proven[0], proven[1]):
        raise ReconcileError("public_dev_runtime_identity_not_proven")
    return proven[0]


def _discover_runtime() -> tuple[Path, Path, Path, str]:
    cwd = Path.cwd()
    _require_local_docker(cwd)
    result = _run(
        [
            _tool("docker"),
            "ps",
            "--filter", f"label=com.docker.compose.project={EXPECTED_PROJECT}",
            "--filter", "label=com.docker.compose.service=api",
            "--format", "{{.ID}}",
        ],
        cwd=cwd,
        timeout=60,
    )
    ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(ids) != 1:
        raise ReconcileError("public_api_container_cardinality")
    bindings = [
        line.strip()
        for line in _run([_tool("docker"), "port", ids[0]], cwd=cwd, timeout=60).stdout.splitlines()
        if line.strip()
    ]
    if not bindings or any(
        not re.fullmatch(r"8000/tcp -> (?:0\.0\.0\.0|\[::\]):8210", line)
        for line in bindings
    ):
        raise ReconcileError("dev_api_port_binding_mismatch")

    labels = {
        name: _inspect_value(ids[0], f'{{{{index .Config.Labels "{name}"}}}}', cwd)
        for name in (
            "com.docker.compose.project",
            "com.docker.compose.service",
            "com.docker.compose.project.working_dir",
            "com.docker.compose.project.config_files",
        )
    }
    project = labels["com.docker.compose.project"].strip()
    service = labels["com.docker.compose.service"].strip()
    if project != EXPECTED_PROJECT or service != "api":
        raise ReconcileError("non_dev_runtime_target_blocked")

    working_raw = labels["com.docker.compose.project.working_dir"].strip()
    if not working_raw:
        raise ReconcileError("compose_working_dir_missing")
    runtime_root = _windows_path(working_raw)
    if not runtime_root.is_dir():
        raise ReconcileError("compose_working_dir_not_found")

    config_raw = labels["com.docker.compose.project.config_files"]
    admin_candidates: list[Path] = []
    public_candidates: list[Path] = []
    ordered_paths = _compose_paths(config_raw, runtime_root)
    for path in ordered_paths:
        if path.name.casefold() == ADMIN_OVERRIDE_NAME.casefold() and path.is_file():
            admin_candidates.append(path.resolve())
        if path.name.casefold() == PUBLIC_OVERRIDE_NAME.casefold() and path.is_file():
            public_candidates.append(path)
    if len(admin_candidates) != 1:
        raise ReconcileError("admin_override_not_unique")
    if len(public_candidates) > 1:
        raise ReconcileError("public_dev_runtime_identity_not_proven")
    if public_candidates:
        public_override = _validate_public_override(runtime_root, public_candidates[0])
        if not ordered_paths or not _same_path(ordered_paths[-1], public_candidates[0]):
            raise ReconcileError("public_dev_override_not_last")
    else:
        public_override = _recover_public_override_from_siblings(
            runtime_root,
            admin_candidates[0],
            cwd,
        )
    return runtime_root.resolve(strict=True), admin_candidates[0], public_override, project


def _origin_is_expected(raw: str) -> bool:
    value = raw.strip().replace("\\", "/").rstrip("/")
    value = re.sub(r"\.git$", "", value, flags=re.IGNORECASE).casefold()
    expected = EXPECTED_REPOSITORY.casefold()
    return value in {
        f"https://github.com/{expected}",
        f"git@github.com:{expected}",
        f"ssh://git@github.com/{expected}",
    }


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run([_tool("git"), "-C", str(repo), *args], cwd=repo, timeout=180, check=check)


def _sync_runtime_repo(runtime_root: Path, expected_sha: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        raise ReconcileError("expected_sha_invalid")

    origin = _git(runtime_root, "remote", "get-url", "origin").stdout.strip()
    if not _origin_is_expected(origin):
        raise ReconcileError("runtime_origin_mismatch")

    tracked = _git(
        runtime_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    ).stdout.strip()
    if tracked:
        raise ReconcileError("runtime_tracked_tree_dirty")

    before = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    _git(runtime_root, "fetch", "--prune", "origin", "main")
    remote_main = _git(runtime_root, "rev-parse", "origin/main").stdout.strip().lower()
    expected = expected_sha.lower()

    expected_on_main = _git(
        runtime_root,
        "merge-base",
        "--is-ancestor",
        expected,
        remote_main,
        check=False,
    )
    if expected_on_main.returncode != 0:
        raise ReconcileError("expected_sha_not_on_origin_main")

    changed = False
    if before != expected:
        can_fast_forward = _git(
            runtime_root,
            "merge-base",
            "--is-ancestor",
            before,
            expected,
            check=False,
        )
        if can_fast_forward.returncode != 0:
            raise ReconcileError("runtime_not_fast_forwardable")
        _git(runtime_root, "merge", "--ff-only", expected)
        changed = True

    after = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    if after != expected:
        raise ReconcileError("runtime_head_mismatch_after_sync")

    tracked_after = _git(
        runtime_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    ).stdout.strip()
    if tracked_after:
        raise ReconcileError("runtime_tracked_tree_dirty_after_sync")

    return {
        "before_sha": before,
        "after_sha": after,
        "origin_main_sha": remote_main,
        "fast_forward_performed": changed,
    }


def _parse_last_json(stdout: str, label: str) -> dict[str, Any]:
    for raw in reversed([line.strip() for line in stdout.splitlines() if line.strip()]):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ReconcileError(f"{label}_json_missing")


def _recreate_api(
    runtime_root: Path,
    admin_override: Path,
    public_override: Path,
    expected_sha: str,
    vault_name: str,
    expected_tenant_id: str,
) -> dict[str, Any]:
    teams_override = (runtime_root / TEAMS_OVERRIDE_REL).resolve()
    if not teams_override.is_file():
        raise ReconcileError("teams_override_missing")

    app_id, bot_secret = provision._load_existing_bot_secret(
        vault_name,
        expected_tenant_id,
    )
    child_env = os.environ.copy()
    child_env["TEAMS_BOT_APP_ID"] = app_id
    child_env["TEAMS_BOT_APP_TENANT_ID"] = expected_tenant_id
    child_env["TEAMS_BOT_SECRET"] = bot_secret
    mutation_state = "attempted_unknown"
    try:
        result = _run(
            [
                sys.executable,
                str(runtime_root / "scripts" / "recreate_cofre_dev_pc24x7.py"),
                "--repo-root",
                str(runtime_root),
                "--expected-sha",
                expected_sha,
                "--admin-override",
                str(admin_override),
                "--runtime-profile",
                PUBLIC_RUNTIME_PROFILE,
                "--public-dev-override",
                str(public_override),
                "--teams-override",
                str(teams_override),
                "--health-timeout",
                "240",
            ],
            cwd=runtime_root,
            env=child_env,
            timeout=720,
            sensitive=True,
            check=False,
        )
        try:
            payload = _parse_last_json(
                result.stdout if result.returncode == 0 else result.stderr,
                "recreate",
            )
        except ReconcileError:
            raise ReconcileError(
                "recreate_json_invalid", mutation_state="attempted_unknown"
            ) from None
        child_state = str(payload.get("mutation_state") or "").strip()
        if child_state not in {
            "not_attempted", "attempted_unknown",
            "attempted_unverified", "verified",
        }:
            child_state = "attempted_unknown"
        if result.returncode != 0:
            code = str(payload.get("error_code") or "recreate_failed")
            if not re.fullmatch(r"[a-z0-9_]+", code):
                code = "recreate_failed"
            raise ReconcileError(code, mutation_state=child_state)
        if child_state != "verified":
            raise ReconcileError(
                "recreate_not_verified", mutation_state=child_state
            )
        return payload
    except ReconcileError as exc:
        state = exc.mutation_state
        if mutation_state != "not_attempted" and state == "not_attempted":
            state = mutation_state
        raise ReconcileError(str(exc), mutation_state=state) from None
    finally:
        child_env["TEAMS_BOT_SECRET"] = ""
        bot_secret = ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _probe_json(
    path: str,
    timeout: float = 20.0,
    *,
    require_envelope: bool = False,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{DEV_API_PORT}{path}",
        headers={"Accept": "application/json", "User-Agent": "reqsys-pc24x7-reconcile/1.0"},
    )
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect).open(request, timeout=timeout) as response:
            if int(response.status) != 200:
                raise ReconcileError(f"runtime_probe_http_{response.status}")
            payload = json.loads(response.read(262_144).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ReconcileError("runtime_probe_failed") from exc
    if not isinstance(payload, dict):
        raise ReconcileError("runtime_probe_payload_invalid")
    if require_envelope and ("data" not in payload or not isinstance(payload.get("data"), dict)):
        raise ReconcileError("runtime_probe_envelope_invalid")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ReconcileError("runtime_probe_data_invalid")
    return data


def _verify_runtime(expected_sha: str) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    last_build = ""
    while time.monotonic() < deadline:
        try:
            build = _probe_json("/api/runtime/build-info")
            last_build = str(build.get("build_sha") or "").strip().lower()
            health = _probe_json("/api/runtime/health")
            auth = _probe_json("/v1/auth/config", require_envelope=True)
            demo = auth.get("demo_login_enabled")
            if demo is not False:
                raise ReconcileError("public_auth_demo_login_not_false")
            if last_build == expected_sha.lower():
                return {
                    "build_sha": last_build,
                    "health_status": str(health.get("status") or "unknown"),
                    "demo_login_enabled": False,
                    "auth_contract_consistent": True,
                }
        except ReconcileError:
            pass
        time.sleep(2)
    raise ReconcileError(f"runtime_same_sha_timeout:{last_build or 'missing'}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise ReconcileError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != "dev":
        raise ReconcileError("environment_must_be_dev")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.expected_sha):
        raise ReconcileError("expected_sha_invalid")
    _require_host()

    runtime_root, admin_override, public_override, project = _discover_runtime()
    sync = _sync_runtime_repo(runtime_root, args.expected_sha)
    public_override = _validate_public_override(runtime_root, public_override, args.expected_sha)
    recreate = _recreate_api(
        runtime_root,
        admin_override,
        public_override,
        args.expected_sha,
        args.vault_name,
        args.expected_tenant_id,
    )
    try:
        runtime = _verify_runtime(args.expected_sha)
    except ReconcileError as exc:
        raise ReconcileError(
            str(exc), mutation_state="attempted_unverified"
        ) from None
    except Exception:
        raise ReconcileError(
            "runtime_verify_unknown",
            mutation_state="attempted_unknown",
        ) from None

    evidence = {
        "schema_version": "1.0.0",
        "status": "ready",
        "environment": "dev",
        "host": EXPECTED_HOST,
        "project": project,
        "correlation_id": args.correlation_id,
        "expected_sha": args.expected_sha.lower(),
        "runtime_root_discovered_from_compose": True,
        "admin_override_reused": True,
        "teams_override_reused": True,
        "public_dev_override_reused": True,
        "runtime_profile": PUBLIC_RUNTIME_PROFILE,
        "sync": sync,
        "recreate": recreate,
        "runtime": runtime,
        "secret_value_exposed": False,
        "production_touched": False,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--expected-tenant-id", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        execute(args)
        return 0
    except Exception as exc:
        failure = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "expected_sha": args.expected_sha,
            "reason": type(exc).__name__,
            "error_code": str(exc) if isinstance(exc, ReconcileError) else "unexpected_error",
            "mutation_state": str(
                getattr(exc, "mutation_state", "unknown")
            ),
            "mutation_performed": bool(
                getattr(exc, "mutation_performed", False)
            ),
            "validation_failed_after_mutation": bool(
                getattr(exc, "mutation_performed", False)
            ),
            "secret_value_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

