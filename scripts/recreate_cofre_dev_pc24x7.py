#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import socket
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
PUBLIC_DEV_OVERRIDE_REL = Path("docker-compose.pc24x7-public-dev.yml")
DEV_API_PORT = "8210"
EXPECTED_HOST = "DESKTOP-PDQK954"


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
    labels["com.docker.compose.project.working_dir"] = _inspect_value(
        container,
        '{{index .Config.Labels "com.docker.compose.project.working_dir"}}',
        cwd=cwd,
    )
    labels["com.docker.compose.project.config_files"] = _inspect_value(
        container,
        '{{index .Config.Labels "com.docker.compose.project.config_files"}}',
        cwd=cwd,
    )
    return {
        "Mounts": mounts,
        "Labels": labels,
        "RuntimeSha": _selected_value(container, "GITHUB_SHA", cwd=cwd),
        "AllowDemoLogin": _selected_value(
            container, "ALLOW_DEMO_LOGIN", cwd=cwd
        ),
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


def _validate_no_reparse_ancestors(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    chain = [absolute, *absolute.parents]
    for item in reversed(chain):
        if not item.exists():
            raise RecreateError("public_dev_override_metadata_unreadable")
        if _has_reparse_point(item):
            raise RecreateError("public_dev_override_reparse_blocked")


def _lexical_public_override(repo_root: Path, candidate: Path) -> Path:
    root_raw = str(repo_root)
    raw = str(candidate)
    for value in (root_raw, raw):
        if (
            not value
            or value.startswith(("\\\\", "//"))
            or re.match(r"^[A-Za-z]:[^\\/]", value)
            or re.search(r"[\\/]{2,}", value)
            or ".." in PureWindowsPath(value).parts
            or ":" in value[2:]
        ):
            raise RecreateError("public_dev_override_path_unsafe")
    root_abs = Path(os.path.abspath(repo_root))
    candidate_abs = Path(os.path.abspath(candidate))
    expected_abs = root_abs / PUBLIC_DEV_OVERRIDE_REL
    if os.path.normcase(str(candidate_abs)) != os.path.normcase(str(expected_abs)):
        raise RecreateError("public_dev_override_not_canonical")
    _validate_no_reparse_ancestors(root_abs)
    _validate_no_reparse_ancestors(candidate_abs)
    return candidate_abs


def validate_public_override(repo_root: Path, candidate: Path, expected_sha: str) -> Path:
    lexical = _lexical_public_override(repo_root, candidate)
    resolved_root = repo_root.resolve(strict=True)
    resolved = lexical.resolve(strict=True)
    if resolved.parent != resolved_root:
        raise RecreateError("public_dev_override_outside_repo")
    rel = PUBLIC_DEV_OVERRIDE_REL.as_posix()
    tracked_blob = run(["git", "rev-parse", f"{expected_sha}:{rel}"], cwd=resolved_root, timeout=30).stdout.strip()
    observed_blob = run(
        ["git", "hash-object", "--path", rel, str(lexical)],
        cwd=resolved_root,
        timeout=30,
    ).stdout.strip()
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


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(Path(os.path.abspath(left)))) == os.path.normcase(
        str(Path(os.path.abspath(right)))
    )


def _compose_paths(raw: str, cwd: Path) -> list[Path]:
    paths: list[Path] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = cwd / path
        paths.append(path)
    return paths


def _prove_public_overlay_from_siblings(
    *, cwd: Path, public_override: Path, admin_override: Path
) -> None:
    for service in ("frontend", "nginx"):
        ids = [
            line.strip()
            for line in run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"label=com.docker.compose.project={DEFAULT_PROJECT}",
                    "--filter",
                    f"label=com.docker.compose.service={service}",
                    "--format",
                    "{{.ID}}",
                ],
                cwd=cwd,
                timeout=60,
                env=_clean_child_env(""),
            ).stdout.splitlines()
            if line.strip()
        ]
        if len(ids) != 1:
            raise RecreateError("public_runtime_recovery_identity_not_proven")
        labels = {
            name: _inspect_value(
                ids[0], f'{{{{index .Config.Labels "{name}"}}}}', cwd=cwd
            )
            for name in (
                "com.docker.compose.project",
                "com.docker.compose.service",
                "com.docker.compose.project.working_dir",
                "com.docker.compose.project.config_files",
            )
        }
        files = _compose_paths(
            labels["com.docker.compose.project.config_files"], cwd
        )
        if (
            labels["com.docker.compose.project"] != DEFAULT_PROJECT
            or labels["com.docker.compose.service"] != service
            or not _same_path(
                Path(labels["com.docker.compose.project.working_dir"]), cwd
            )
            or len([path for path in files if _same_path(path, public_override)]) != 1
            or not files
            or not _same_path(files[-1], public_override)
            or len([path for path in files if _same_path(path, admin_override)]) != 1
        ):
            raise RecreateError("public_runtime_recovery_identity_not_proven")


def validate_local_docker(
    container: str,
    *,
    cwd: Path,
    public_override: Path,
    admin_override: Path | None = None,
) -> None:
    if os.name != "nt" or socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise RecreateError("public_runtime_host_not_allowed")
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
    labels = {
        name: _inspect_value(
            ids[0], f'{{{{index .Config.Labels "{name}"}}}}', cwd=cwd
        )
        for name in (
            "com.docker.compose.project",
            "com.docker.compose.service",
            "com.docker.compose.project.working_dir",
            "com.docker.compose.project.config_files",
        )
    }
    if (
        labels["com.docker.compose.project"] != DEFAULT_PROJECT
        or labels["com.docker.compose.service"] != "api"
    ):
        raise RecreateError("public_runtime_compose_identity_mismatch")
    observed_root = Path(os.path.abspath(labels["com.docker.compose.project.working_dir"]))
    if os.path.normcase(str(observed_root)) != os.path.normcase(str(cwd)):
        raise RecreateError("public_runtime_working_dir_mismatch")
    observed_files = _compose_paths(
        labels["com.docker.compose.project.config_files"], cwd
    )
    public_files = [
        path for path in observed_files if _same_path(path, public_override)
    ]
    if len(public_files) > 1 or (
        public_files and not _same_path(observed_files[-1], public_override)
    ):
        raise RecreateError("public_runtime_override_not_last")
    if not public_files:
        if admin_override is None or len(
            [path for path in observed_files if _same_path(path, admin_override)]
        ) != 1:
            raise RecreateError("public_runtime_recovery_identity_not_proven")
        _prove_public_overlay_from_siblings(
            cwd=cwd,
            public_override=public_override,
            admin_override=admin_override,
        )
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
    if args.runtime_profile != PUBLIC_RUNTIME_PROFILE:
        raise RecreateError("public_runtime_profile_required")
    repo_root_lexical = Path(os.path.abspath(args.repo_root))
    if git_head(repo_root_lexical) != args.expected_sha:
        raise RecreateError("git_head_mismatch")
    if args.public_dev_override is None:
        raise RecreateError("public_dev_override_required")
    if args.project != DEFAULT_PROJECT or args.container != DEFAULT_CONTAINER:
        raise RecreateError("non_dev_runtime_target_blocked")
    public_override = validate_public_override(
        repo_root_lexical, args.public_dev_override, args.expected_sha
    )
    repo_root = repo_root_lexical.resolve(strict=True)
    if not args.secret_file.is_file():
        raise RecreateError("cofre_secret_file_missing")
    if not args.admin_override.is_file() or not args.teams_override.is_file():
        raise RecreateError("required_runtime_override_missing")
    validate_local_docker(
        args.container,
        cwd=repo_root,
        public_override=public_override,
        admin_override=args.admin_override.resolve(),
    )

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
    rendered = run(
        [*base, "config", "--format", "json"],
        cwd=repo_root,
        timeout=120,
        env=child_env,
    )
    validate_rendered_public_auth(rendered.stdout)

    mutation_state = "attempted_unknown"
    try:
        run(
            [*base, "up", "-d", "--no-deps", "--build", "--force-recreate", "api"],
            cwd=repo_root,
            timeout=600,
            env=child_env,
        )
        mutation_state = "attempted_unverified"
        health = wait_healthy(
            args.container, cwd=repo_root, timeout_seconds=args.health_timeout
        )
        item = inspect_container(args.container, cwd=repo_root)
        auth_demo = probe_auth_config()
        labels = item.get("Labels") or {}
        mounts = item.get("Mounts") or []
        secret_mount = [
            mount
            for mount in mounts
            if mount.get("Destination") == "/run/secrets/cofre_keyring_passphrase"
        ]
        data_mount = [
            mount for mount in mounts if mount.get("Destination") == "/data"
        ]
        backend_mount = [
            mount for mount in mounts if mount.get("Destination") == "/app"
        ]
        observed_sha = str(item.get("RuntimeSha") or "").strip().lower()
        if observed_sha != args.expected_sha.lower():
            raise RecreateError("runtime_sha_mismatch")
        if item.get("AllowDemoLogin", "").strip().lower() != "false":
            raise RecreateError("runtime_container_demo_login_not_false")
        if auth_demo is not False:
            raise RecreateError("runtime_api_demo_login_not_false")
        if labels.get("com.docker.compose.project") != args.project:
            raise RecreateError("compose_project_mismatch")
        if labels.get("com.docker.compose.service") != "api":
            raise RecreateError("compose_service_mismatch")
        if not secret_mount or secret_mount[0].get("RW") is not False:
            raise RecreateError("secret_mount_not_read_only")
        if (
            not data_mount
            or data_mount[0].get("Type") != "volume"
            or data_mount[0].get("RW") is not True
        ):
            raise RecreateError("persistent_data_mount_missing")
        expected_backend = str((repo_root / "backend").resolve()).replace(
            "\\", "/"
        ).lower()
        actual_backend = str(
            backend_mount[0].get("Source") if backend_mount else ""
        ).replace("\\", "/").lower()
        docker_desktop_backend = expected_backend.replace(
            "c:/", "/run/desktop/mnt/host/c/"
        )
        if (
            not actual_backend.endswith(docker_desktop_backend)
            and expected_backend not in actual_backend
        ):
            raise RecreateError("backend_bind_not_current_worktree")
        mutation_state = "verified"
    except RecreateError as exc:
        state = exc.mutation_state
        if mutation_state != "not_attempted" and state == "not_attempted":
            state = mutation_state
        raise RecreateError(str(exc), mutation_state=state) from None
    except Exception:
        raise RecreateError(
            "runtime_mutation_state_unknown", mutation_state=mutation_state
        ) from None

    return {
        "ok": True,
        "environment": "dev",
        "project": args.project,
        "service": "api",
        "container": args.container,
        "runtime_sha": observed_sha,
        "health": health,
        "runtime_profile": args.runtime_profile,
        "allow_demo_login": False,
        "compose_auth_contract_valid": True,
        "mutation_state": mutation_state,
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
