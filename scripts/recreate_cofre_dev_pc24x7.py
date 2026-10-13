#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PureWindowsPath

DEFAULT_PROJECT = "wt-pc24x7-piloto"
DEFAULT_CONTAINER = "wt-pc24x7-piloto-api-1"
DEFAULT_SECRET_FILE = Path(r"C:\ProgramData\ReqSys\secrets\cofre-keyring-passphrase.txt")
PUBLIC_RUNTIME_PROFILE = "pc24x7-public-dev"
LOCAL_DEMO_PROFILE = "teams-local-demo"
PUBLIC_DEV_OVERRIDE_REL = Path("docker-compose.pc24x7-public-dev.yml")
DEV_API_PORT = "8210"


class RecreateError(RuntimeError):
    def __init__(self, message: str, *, mutation_state: str = "not_attempted") -> None:
        super().__init__(message)
        self.mutation_state = mutation_state
        self.mutation_performed = mutation_state != "not_attempted"


def run(args: list[str], *, cwd: Path, timeout: int = 300, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RecreateError(f"command_failed:{args[0]}:exit_{completed.returncode}")
    return completed


def git_head(repo_root: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=30).stdout.strip()


def _inspect_value(container: str, template: str, *, cwd: Path) -> str:
    return run(
        ["docker", "inspect", "--format", template, container],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()


def _selected_value(container: str, name: str, *, cwd: Path) -> str:
    return run(
        ["docker", "exec", container, "printenv", name],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()


def inspect_container(container: str, *, cwd: Path) -> dict:
    """Return only contract fields; never materialize full state, logs or environment."""
    mounts = json.loads(_inspect_value(container, "{{json .Mounts}}", cwd=cwd))
    labels = {
        "com.docker.compose.project": _inspect_value(
            container, '{{index .Config.Labels "com.docker.compose.project"}}', cwd=cwd
        ),
        "com.docker.compose.service": _inspect_value(
            container, '{{index .Config.Labels "com.docker.compose.service"}}', cwd=cwd
        ),
    }
    return {
        "Mounts": mounts,
        "Labels": labels,
        "RuntimeSha": _selected_value(container, "GITHUB_SHA", cwd=cwd),
    }


def wait_healthy(container: str, *, cwd: Path, timeout_seconds: int = 180) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        health = _inspect_value(container, "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", cwd=cwd)
        last = health.strip().lower() or "unknown"
        if last == "healthy":
            return last
        time.sleep(2)
    raise RecreateError("container_health_timeout", mutation_state="attempted_unknown")


def _has_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RecreateError("public_dev_override_metadata_unreadable") from exc
    attrs = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _lexical_public_override(repo_root: Path, candidate: Path) -> Path:
    raw = str(candidate)
    if (
        not raw
        or raw.startswith(("\\\\", "//"))
        or re.match(r"^[A-Za-z]:[^\\/]", raw)
        or re.search(r"[\\/]{2,}", raw)
        or ".." in PureWindowsPath(raw).parts
        or ":" in raw[2:]
    ):
        raise RecreateError("public_dev_override_path_unsafe")
    root_abs = Path(os.path.abspath(repo_root))
    candidate_abs = Path(os.path.abspath(candidate))
    expected_abs = root_abs / PUBLIC_DEV_OVERRIDE_REL
    if os.path.normcase(str(candidate_abs)) != os.path.normcase(str(expected_abs)):
        raise RecreateError("public_dev_override_not_canonical")
    cursor = root_abs
    if _has_reparse_point(cursor):
        raise RecreateError("public_dev_override_reparse_blocked")
    for part in PUBLIC_DEV_OVERRIDE_REL.parts:
        cursor = cursor / part
        if _has_reparse_point(cursor):
            raise RecreateError("public_dev_override_reparse_blocked")
    return candidate_abs


def validate_public_override(repo_root: Path, candidate: Path, expected_sha: str) -> Path:
    lexical = _lexical_public_override(repo_root, candidate)
    resolved_root = repo_root.resolve(strict=True)
    resolved = lexical.resolve(strict=True)
    if resolved.parent != resolved_root:
        raise RecreateError("public_dev_override_outside_repo")
    rel = PUBLIC_DEV_OVERRIDE_REL.as_posix()
    tracked_blob = run(["git", "rev-parse", f"{expected_sha}:{rel}"], cwd=resolved_root, timeout=30).stdout.strip()
    observed_blob = run(["git", "hash-object", "--no-filters", str(lexical)], cwd=resolved_root, timeout=30).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", tracked_blob) or observed_blob != tracked_blob:
        raise RecreateError("public_dev_override_head_mismatch")
    return resolved


def _clean_child_env(expected_sha: str) -> dict[str, str]:
    child = os.environ.copy()
    for name in (
        "DOCKER_HOST", "DOCKER_CONTEXT",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        child.pop(name, None)
    child["NO_PROXY"] = "127.0.0.1,localhost"
    child["no_proxy"] = "127.0.0.1,localhost"
    child["REQSYS_BUILD_SHA"] = expected_sha
    return child


def validate_local_docker(container: str, *, cwd: Path) -> None:
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise RecreateError("docker_environment_override_blocked")
    endpoint_raw = run(
        ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        cwd=cwd,
        timeout=60,
        env=_clean_child_env(""),
    ).stdout.strip()
    try:
        endpoint = str(json.loads(endpoint_raw)).lower()
    except json.JSONDecodeError as exc:
        raise RecreateError("docker_context_invalid") from exc
    if endpoint != "npipe:////./pipe/docker_engine":
        raise RecreateError("docker_remote_context_blocked")
    ids = [
        line.strip()
        for line in run(
            [
                "docker", "ps",
                "--filter", f"label=com.docker.compose.project={DEFAULT_PROJECT}",
                "--filter", "label=com.docker.compose.service=api",
                "--format", "{{.ID}}",
            ],
            cwd=cwd,
            timeout=60,
            env=_clean_child_env(""),
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise RecreateError("public_api_container_cardinality")
    observed_name = _inspect_value(ids[0], "{{.Name}}", cwd=cwd).lstrip("/")
    if observed_name != container:
        raise RecreateError("public_api_container_identity_mismatch")
    bindings = [
        line.strip()
        for line in run(
            ["docker", "port", container],
            cwd=cwd,
            timeout=60,
            env=_clean_child_env(""),
        ).stdout.splitlines()
        if line.strip()
    ]
    if not bindings or any(
        not re.fullmatch(r"8000/tcp -> (?:0\.0\.0\.0|\[::\]):8210", line)
        for line in bindings
    ):
        raise RecreateError("dev_api_port_binding_mismatch")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_auth_config() -> bool:
    request = urllib.request.Request(
        f"http://127.0.0.1:{DEV_API_PORT}/v1/auth/config",
        headers={"Accept": "application/json", "User-Agent": "reqsys-public-dev-auth/1.0"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    try:
        with opener.open(request, timeout=20) as response:
            if int(response.status) != 200:
                raise RecreateError("auth_config_http_invalid", mutation_state="attempted_unverified")
            payload = json.loads(response.read(262_144).decode("utf-8"))
    except RecreateError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RecreateError("auth_config_probe_failed", mutation_state="attempted_unverified") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise RecreateError("auth_config_envelope_invalid", mutation_state="attempted_unverified")
    if payload["data"].get("demo_login_enabled") is not False:
        raise RecreateError("runtime_demo_login_not_false", mutation_state="attempted_unverified")
    return False


def _environment_map(raw: object) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return dict(str(item).split("=", 1) for item in raw if "=" in str(item))
    return {}


def validate_rendered_public_auth(payload: str) -> bool:
    try:
        document = json.loads(payload)
        api = ((document.get("services") or {}).get("api") or {})
        environment = _environment_map(api.get("environment"))
    except (AttributeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RecreateError("compose_config_contract_invalid") from exc
    if environment.get("ALLOW_DEMO_LOGIN", "").strip().lower() != "false":
        raise RecreateError("public_dev_demo_login_contract_invalid")
    return False


def build_files(
    repo_root: Path,
    admin_override: Path,
    teams_override: Path,
    sha_override: Path,
    public_override: Path | None,
) -> list[Path]:
    files = [
        repo_root / "docker-compose.yml",
        repo_root / "docker-compose.dev.yml",
        admin_override,
        teams_override,
        repo_root / "docker-compose.pc24x7-cofre.yml",
        sha_override,
    ]
    if public_override is not None:
        files.append(public_override)
    return files


def compose_args(project: str, files: list[Path]) -> list[str]:
    args = ["docker", "compose", "-p", project]
    for path in files:
        args.extend(["-f", str(path)])
    return args


def execute(args: argparse.Namespace) -> dict:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.expected_sha):
        raise RecreateError("expected_sha_invalid")
    if args.runtime_profile not in {PUBLIC_RUNTIME_PROFILE, LOCAL_DEMO_PROFILE}:
        raise RecreateError("runtime_profile_invalid")
    is_public = args.runtime_profile == PUBLIC_RUNTIME_PROFILE
    repo_root = args.repo_root.resolve()
    if git_head(repo_root) != args.expected_sha:
        raise RecreateError("git_head_mismatch")
    public_override = None
    if is_public:
        if args.public_dev_override is None:
            raise RecreateError("public_dev_override_required")
        if args.project != DEFAULT_PROJECT or args.container != DEFAULT_CONTAINER:
            raise RecreateError("non_dev_runtime_target_blocked")
        public_override = validate_public_override(
            repo_root, args.public_dev_override, args.expected_sha
        )
        validate_local_docker(args.container, cwd=repo_root)
    elif args.project == DEFAULT_PROJECT or args.container == DEFAULT_CONTAINER:
        raise RecreateError("local_demo_identity_conflicts_with_public")
    if not args.secret_file.is_file():
        raise RecreateError("cofre_secret_file_missing")
    if not args.admin_override.is_file() or not args.teams_override.is_file():
        raise RecreateError("required_runtime_override_missing")

    temp_dir = repo_root / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    sha_override = temp_dir / "cofre-runtime-sha.override.yml"
    sha_override.write_text(
        "services:\n"
        "  api:\n"
        "    environment:\n"
        f'      GITHUB_SHA: "{args.expected_sha}"\n',
        encoding="utf-8",
    )

    files = build_files(
        repo_root,
        args.admin_override.resolve(),
        args.teams_override.resolve(),
        sha_override,
        public_override,
    )
    base = compose_args(args.project, files)
    child_env = _clean_child_env(args.expected_sha)
    rendered = run([*base, "config", "--format", "json"], cwd=repo_root, timeout=120, env=child_env)
    if is_public:
        validate_rendered_public_auth(rendered.stdout)

    mutation_state = "not_attempted"
    try:
        mutation_state = "attempted_unknown"
        run(
            [*base, "up", "-d", "--no-deps", "--build", "--force-recreate", "api"],
            cwd=repo_root,
            timeout=600,
            env=child_env,
        )
        mutation_state = "attempted_unverified"
        health = wait_healthy(args.container, cwd=repo_root, timeout_seconds=args.health_timeout)
        item = inspect_container(args.container, cwd=repo_root)
        auth_demo = probe_auth_config() if is_public else None
    except RecreateError as exc:
        if exc.mutation_state == "not_attempted" and mutation_state != "not_attempted":
            raise RecreateError("runtime_validation_failed", mutation_state=mutation_state) from exc
        raise
    except Exception as exc:
        raise RecreateError("runtime_mutation_state_unknown", mutation_state=mutation_state) from exc

    labels = item.get("Labels") or {}
    mounts = item.get("Mounts") or []

    secret_mount = [
        m for m in mounts
        if m.get("Destination") == "/run/secrets/cofre_keyring_passphrase"
    ]
    data_mount = [m for m in mounts if m.get("Destination") == "/data"]
    backend_mount = [m for m in mounts if m.get("Destination") == "/app"]

    observed_sha = str(item.get("RuntimeSha") or "").strip().lower()
    if observed_sha != args.expected_sha.lower():
        raise RecreateError("runtime_sha_mismatch", mutation_state="attempted_unverified")
    if is_public and auth_demo is not False:
        raise RecreateError("runtime_demo_login_not_false", mutation_state="attempted_unverified")
    if labels.get("com.docker.compose.project") != args.project:
        raise RecreateError("compose_project_mismatch")
    if labels.get("com.docker.compose.service") != "api":
        raise RecreateError("compose_service_mismatch")
    if not secret_mount or secret_mount[0].get("RW") is not False:
        raise RecreateError("secret_mount_not_read_only")
    if not data_mount or data_mount[0].get("Type") != "volume" or data_mount[0].get("RW") is not True:
        raise RecreateError("persistent_data_mount_missing")
    expected_backend = str((repo_root / "backend").resolve()).replace("\\", "/").lower()
    actual_backend = str((backend_mount[0].get("Source") if backend_mount else "")).replace("\\", "/").lower()
    if not actual_backend.endswith(expected_backend.replace("c:/", "/run/desktop/mnt/host/c/")) and expected_backend not in actual_backend:
        raise RecreateError("backend_bind_not_current_worktree")

    return {
        "ok": True,
        "environment": "dev",
        "project": args.project,
        "service": "api",
        "container": args.container,
        "runtime_sha": observed_sha,
        "health": health,
        "runtime_profile": args.runtime_profile,
        "allow_demo_login": False if is_public else None,
        "compose_auth_contract_valid": True if is_public else None,
        "mutation_state": "verified",
        "mutation_performed": True,
        "secret_file_exists": True,
        "secret_value_observed": False,
        "secret_mount_read_only": True,
        "data_volume_persistent": True,
        "backend_bound_to_current_worktree": True,
        "production_touched": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild/recreate governado da API DEV PC24x7 com Cofre")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--runtime-profile", required=True)
    parser.add_argument("--public-dev-override", type=Path)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--admin-override", type=Path, required=True)
    parser.add_argument("--teams-override", type=Path, required=True)
    parser.add_argument("--health-timeout", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error_code": str(exc) if isinstance(exc, RecreateError) else "unexpected_error",
            "mutation_state": str(getattr(exc, "mutation_state", "unknown")),
            "mutation_performed": bool(getattr(exc, "mutation_performed", False)),
            "validation_failed_after_mutation": str(getattr(exc, "mutation_state", "unknown")) != "not_attempted",
            "secret_value_observed": False,
            "production_touched": False,
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
