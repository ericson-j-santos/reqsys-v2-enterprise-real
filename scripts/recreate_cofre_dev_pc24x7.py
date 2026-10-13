#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_PROJECT = "wt-pc24x7-piloto"
DEFAULT_CONTAINER = "wt-pc24x7-piloto-api-1"
DEFAULT_SECRET_FILE = Path(r"C:\ProgramData\ReqSys\secrets\cofre-keyring-passphrase.txt")
PUBLIC_RUNTIME_PROFILE = "pc24x7-public-dev"
PUBLIC_DEV_OVERRIDE_REL = Path("docker-compose.pc24x7-public-dev.yml")
DEV_API_PORT = "8210"


class RecreateError(RuntimeError):
    def __init__(self, message: str, *, mutation_performed: bool = False) -> None:
        super().__init__(message)
        self.mutation_performed = mutation_performed


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


def inspect_container(container: str, *, cwd: Path) -> dict:
    """Return only fields required by the contract; never materialize Config.Env."""
    state = json.loads(_inspect_value(container, "{{json .State}}", cwd=cwd))
    mounts = json.loads(_inspect_value(container, "{{json .Mounts}}", cwd=cwd))
    labels = {
        "com.docker.compose.project": _inspect_value(
            container, '{{index .Config.Labels "com.docker.compose.project"}}', cwd=cwd
        ),
        "com.docker.compose.service": _inspect_value(
            container, '{{index .Config.Labels "com.docker.compose.service"}}', cwd=cwd
        ),
    }
    demo = run(
        [
            "docker", "exec", container, "python", "-c",
            "import os; print(os.environ.get('ALLOW_DEMO_LOGIN', ''))",
        ],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()
    return {"State": state, "Mounts": mounts, "Labels": labels, "AllowDemoLogin": demo}


def wait_healthy(container: str, *, cwd: Path, timeout_seconds: int = 180) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        item = inspect_container(container, cwd=cwd)
        state = item.get("State") or {}
        health = state.get("Health") or {}
        last = str(health.get("Status") or state.get("Status") or "unknown").lower()
        if last == "healthy":
            return last
        time.sleep(2)
    raise RecreateError(f"container_health_timeout:{last}")


def _has_reparse_point(path: Path) -> bool:
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError as exc:
        raise RecreateError("public_dev_override_metadata_unreadable") from exc
    marker = getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attrs & marker)


def validate_public_override(repo_root: Path, candidate: Path) -> Path:
    raw = str(candidate)
    if raw.startswith(("\\\\", "//")) or re.match(r"^[A-Za-z]:[^\\/]", raw):
        raise RecreateError("public_dev_override_path_unsafe")
    if ":" in raw[2:]:
        raise RecreateError("public_dev_override_ads_blocked")
    expected = (repo_root / PUBLIC_DEV_OVERRIDE_REL).resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved != expected or repo_root != resolved.parent:
        raise RecreateError("public_dev_override_not_canonical")
    current = resolved
    while True:
        if _has_reparse_point(current):
            raise RecreateError("public_dev_override_reparse_blocked")
        if current == repo_root:
            break
        if repo_root not in current.parents:
            raise RecreateError("public_dev_override_outside_repo")
        current = current.parent
    run(
        ["git", "ls-files", "--error-unmatch", PUBLIC_DEV_OVERRIDE_REL.as_posix()],
        cwd=repo_root,
        timeout=30,
    )
    return resolved


def validate_local_docker(container: str, *, cwd: Path) -> None:
    endpoint_raw = run(
        ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        cwd=cwd,
        timeout=60,
    ).stdout.strip()
    try:
        endpoint = str(json.loads(endpoint_raw))
    except json.JSONDecodeError as exc:
        raise RecreateError("docker_context_invalid") from exc
    if not endpoint.lower().startswith("npipe://"):
        raise RecreateError("docker_remote_context_blocked")
    bindings = [
        line.strip()
        for line in run(["docker", "port", container, "8000/tcp"], cwd=cwd, timeout=60).stdout.splitlines()
        if line.strip()
    ]
    if not bindings or any(not line.endswith(f":{DEV_API_PORT}") for line in bindings):
        raise RecreateError("dev_api_port_binding_mismatch")


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
    public_override: Path,
) -> list[Path]:
    return [
        repo_root / "docker-compose.yml",
        repo_root / "docker-compose.dev.yml",
        admin_override,
        teams_override,
        repo_root / "docker-compose.pc24x7-cofre.yml",
        sha_override,
        public_override,
    ]


def compose_args(project: str, files: list[Path]) -> list[str]:
    args = ["docker", "compose", "-p", project]
    for path in files:
        args.extend(["-f", str(path)])
    return args


def execute(args: argparse.Namespace) -> dict:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.expected_sha):
        raise RecreateError("expected_sha_invalid")
    if args.runtime_profile != PUBLIC_RUNTIME_PROFILE:
        raise RecreateError("public_runtime_profile_required")
    repo_root = args.repo_root.resolve()
    public_override = validate_public_override(repo_root, args.public_dev_override)
    validate_local_docker(args.container, cwd=repo_root)
    if git_head(repo_root) != args.expected_sha:
        raise RecreateError("git_head_mismatch")
    if not args.secret_file.is_file():
        raise RecreateError("cofre_secret_file_missing")
    if args.project != DEFAULT_PROJECT or args.container != DEFAULT_CONTAINER:
        raise RecreateError("non_dev_runtime_target_blocked")
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
    child_env = os.environ.copy()
    child_env["REQSYS_BUILD_SHA"] = args.expected_sha
    rendered = run([*base, "config", "--format", "json"], cwd=repo_root, timeout=120, env=child_env)
    validate_rendered_public_auth(rendered.stdout)

    mutation_performed = False
    try:
        run(
            [*base, "up", "-d", "--no-deps", "--build", "--force-recreate", "api"],
            cwd=repo_root,
            timeout=600,
            env=child_env,
        )
        mutation_performed = True
        health = wait_healthy(args.container, cwd=repo_root, timeout_seconds=args.health_timeout)
        item = inspect_container(args.container, cwd=repo_root)
    except Exception as exc:
        if mutation_performed:
            raise RecreateError(
                "post_recreate_validation_failed",
                mutation_performed=True,
            ) from exc
        raise

    labels = item.get("Labels") or {}
    mounts = item.get("Mounts") or []

    secret_mount = [
        m for m in mounts
        if m.get("Destination") == "/run/secrets/cofre_keyring_passphrase"
    ]
    data_mount = [m for m in mounts if m.get("Destination") == "/data"]
    backend_mount = [m for m in mounts if m.get("Destination") == "/app"]

    if item.get("AllowDemoLogin", "").strip().lower() != "false":
        raise RecreateError("runtime_demo_login_not_false", mutation_performed=True)
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
        "runtime_sha": args.expected_sha,
        "health": health,
        "runtime_profile": PUBLIC_RUNTIME_PROFILE,
        "allow_demo_login": False,
        "compose_auth_contract_valid": True,
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
    parser.add_argument("--public-dev-override", type=Path, required=True)
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
            "error": str(exc),
            "mutation_performed": bool(getattr(exc, "mutation_performed", False)),
            "validation_failed_after_mutation": bool(getattr(exc, "mutation_performed", False)),
            "secret_value_observed": False,
            "production_touched": False,
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
