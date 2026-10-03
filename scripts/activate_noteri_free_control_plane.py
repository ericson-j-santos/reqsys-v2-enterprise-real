#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
WATCHDOG = Path(__file__).resolve().parent / "noteri_control_plane_watchdog.py"
CONFIRM = "ACTIVATE-NOTERI-FREE-CONTROL-PLANE"
INSTALL_CONFIRM = "INSTALL-NOTERI-CONTROL-PLANE-WATCHDOG"

RUNNER_VERSION = "2.337.0"
RUNNER_ASSET_URL = (
    "https://github.com/actions/runner/releases/download/"
    f"v{RUNNER_VERSION}/actions-runner-win-x64-{RUNNER_VERSION}.zip"
)
RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"
RUNNER_NAME = "Noteri"
RUNNER_LABELS = "noteri,reqsys-dev"
EXPECTED_GITHUB_LOGIN = "ericson-j-santos"

CANDIDATES = (
    Path(r"C:\actions-runner"),
    Path(r"C:\dev\actions-runner"),
    Path(r"C:\dev\github-actions-runner"),
    Path(r"C:\dev\runner"),
)


class ActivationError(RuntimeError):
    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def validate_host() -> str:
    if os.name != "nt":
        raise ActivationError("windows_required", "Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise ActivationError("host_not_authorized", f"host não autorizado: {host}")
    machine = platform.machine().casefold()
    if machine not in {"amd64", "x86_64"}:
        raise ActivationError("x64_required", f"arquitetura não suportada: {machine}")
    return host


def runner_binary_contract(root: Path) -> bool:
    return (
        root.is_dir()
        and (root / "config.cmd").is_file()
        and (root / "run.cmd").is_file()
        and (root / "bin" / "Runner.Listener.exe").is_file()
    )


def runner_contract(root: Path) -> bool:
    return runner_binary_contract(root) and (root / ".runner").is_file()


def discover_runner(explicit: Path | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("REQSYS_GITHUB_RUNNER_HOME")
    if env:
        candidates.append(Path(env))
    candidates.extend(CANDIDATES)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "ReqSys" / "NoteriGitHubRunner")
    for base in (Path.home(), Path(r"C:\dev")):
        if not base.is_dir():
            continue
        try:
            for item in base.iterdir():
                if item.is_dir() and "runner" in item.name.casefold():
                    candidates.append(item)
        except OSError:
            pass
    seen: set[str] = set()
    for item in candidates:
        key = os.path.normcase(str(item))
        if key in seen:
            continue
        seen.add(key)
        try:
            if runner_contract(item):
                return item.resolve()
        except OSError:
            continue
    return None


def default_runner_home() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise ActivationError("localappdata_missing", "LOCALAPPDATA não definido")
    return Path(local) / "ReqSys" / "NoteriGitHubRunner"


def find_gh() -> Path | None:
    located = shutil.which("gh")
    if located:
        return Path(located)
    candidates = [
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "GitHub CLI" / "gh.exe",
    ]
    return next((item for item in candidates if item.is_file()), None)


def ensure_gh() -> Path:
    existing = find_gh()
    if existing:
        return existing
    winget = shutil.which("winget")
    if not winget:
        raise ActivationError("github_cli_required", "GitHub CLI ausente e winget indisponível")
    cp = subprocess.run(
        [
            winget,
            "install",
            "--id", "GitHub.cli",
            "-e",
            "--source", "winget",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
        env=gh_env(),
    )
    installed = find_gh()
    if cp.returncode != 0 or installed is None:
        raise ActivationError("github_cli_install_failed", "GitHub CLI não pôde ser instalado automaticamente")
    return installed


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def gh_active_login(gh: Path) -> str:
    cp = subprocess.run(
        [str(gh), "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=gh_env(),
    )
    return cp.stdout.strip() if cp.returncode == 0 else ""


def ensure_gh_auth(gh: Path) -> None:
    status = subprocess.run(
        [str(gh), "auth", "status", "--hostname", "github.com"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        env=gh_env(),
    )
    if status.returncode == 0:
        active = gh_active_login(gh)
        if active.casefold() == EXPECTED_GITHUB_LOGIN.casefold():
            return
        switch = subprocess.run(
            [
                str(gh),
                "auth",
                "switch",
                "--hostname", "github.com",
                "--user", EXPECTED_GITHUB_LOGIN,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
            env=gh_env(),
        )
        if switch.returncode == 0 and gh_active_login(gh).casefold() == EXPECTED_GITHUB_LOGIN.casefold():
            return
    login = subprocess.run(
        [
            str(gh),
            "auth",
            "login",
            "--hostname", "github.com",
            "--git-protocol", "https",
            "--web",
            "--scopes", "repo",
        ],
        timeout=300,
        check=False,
        env=gh_env(),
    )
    if login.returncode != 0:
        raise ActivationError("github_auth_required", "autenticação GitHub não concluída")
    status = subprocess.run(
        [str(gh), "auth", "status", "--hostname", "github.com"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        env=gh_env(),
    )
    if status.returncode != 0 or gh_active_login(gh).casefold() != EXPECTED_GITHUB_LOGIN.casefold():
        raise ActivationError("github_auth_required", "GitHub CLI continua sem autenticação válida")


def refresh_repo_scope(gh: Path) -> None:
    cp = subprocess.run(
        [
            str(gh),
            "auth",
            "refresh",
            "--hostname", "github.com",
            "--scopes", "repo",
        ],
        timeout=300,
        check=False,
        env=gh_env(),
    )
    if cp.returncode != 0:
        raise ActivationError(
            "github_scope_refresh_required",
            "não foi possível atualizar o escopo repo da autenticação GitHub",
        )


def request_registration_token(gh: Path) -> str:
    cp = subprocess.run(
        [
            str(gh),
            "api",
            "--method", "POST",
            f"repos/{REPOSITORY}/actions/runners/registration-token",
            "--jq", ".token",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=gh_env(),
    )
    token = cp.stdout.strip()
    return token if cp.returncode == 0 and len(token) >= 20 else ""


def registration_token(gh: Path) -> str:
    token = request_registration_token(gh)
    if token:
        return token

    refresh_repo_scope(gh)
    if gh_active_login(gh).casefold() != EXPECTED_GITHUB_LOGIN.casefold():
        raise ActivationError(
            "github_account_mismatch",
            "conta GitHub ativa diverge de ericson-j-santos",
        )

    token = request_registration_token(gh)
    if token:
        return token

    raise ActivationError(
        "github_runner_admin_permission_required",
        "token GitHub local não autorizou o endpoint de registro após refresh de escopo",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(zip_path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if root not in destination.parents and destination != root:
                raise ActivationError("runner_archive_invalid", "arquivo do runner contém caminho inválido")
        archive.extractall(target)


def ensure_runner_binaries(root: Path) -> None:
    if runner_binary_contract(root):
        return
    if root.exists() and any(root.iterdir()):
        raise ActivationError("runner_home_not_empty", f"diretório de runner não vazio: {root}")
    root.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        RUNNER_ASSET_URL,
        headers={"User-Agent": "ReqSys-Noteri-Control-Plane-Bootstrap/1.0"},
    )
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        archive_path = Path(handle.name)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        observed = sha256_file(archive_path)
        if observed.casefold() != RUNNER_ASSET_SHA256.casefold():
            raise ActivationError("runner_digest_mismatch", "SHA-256 do runner oficial divergente")
        safe_extract(archive_path, root)
    finally:
        archive_path.unlink(missing_ok=True)
    if not runner_binary_contract(root):
        raise ActivationError("runner_install_incomplete", "binários oficiais do runner incompletos")


def register_runner(root: Path, gh: Path) -> bool:
    if runner_contract(root):
        return False
    token = registration_token(gh)
    try:
        cp = subprocess.run(
            [
                str(root / "config.cmd"),
                "--unattended",
                "--url", REPOSITORY_URL,
                "--token", token,
                "--name", RUNNER_NAME,
                "--labels", RUNNER_LABELS,
                "--work", "_work",
                "--replace",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        if cp.returncode != 0:
            raise ActivationError("runner_registration_failed", "registro do runner falhou")
    finally:
        token = ""
    if not runner_contract(root):
        raise ActivationError("runner_registration_failed", "contrato local do runner não foi criado")
    return True


def provision_runner(explicit: Path | None) -> tuple[Path, bool]:
    gh = ensure_gh()
    ensure_gh_auth(gh)
    root = explicit.resolve() if explicit else default_runner_home().resolve()
    ensure_runner_binaries(root)
    registered = register_runner(root, gh)
    return root, registered


def runner_running() -> bool:
    target = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "tasklist.exe"
    cp = subprocess.run(
        [str(target), "/FI", "IMAGENAME eq Runner.Listener.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    return cp.returncode == 0 and "runner.listener.exe" in cp.stdout.casefold()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-sha")
    parser.add_argument("--runner-home", type=Path)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        emit({"ok": False, "state": "confirmation_invalid"})
        return 2

    registration_performed = False
    registration_token_consumed_in_memory = False
    try:
        host = validate_host()
        repo_root = args.repo_root.resolve()
        source_sha = (args.source_sha or "").strip()
        if not source_sha:
            cp = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            if cp.returncode != 0:
                raise ActivationError("source_sha_unavailable", "source_sha indisponível")
            source_sha = cp.stdout.strip()
        if len(source_sha) != 40:
            raise ActivationError("source_sha_invalid", "source_sha inválido")

        runner = discover_runner(args.runner_home)
        if runner is None:
            runner, registration_performed = provision_runner(args.runner_home)
            registration_token_consumed_in_memory = registration_performed

        cp = subprocess.run(
            [
                sys.executable,
                str(WATCHDOG),
                "install",
                "--repo-root", str(repo_root),
                "--runner-home", str(runner),
                "--source-sha", source_sha,
                "--confirm", INSTALL_CONFIRM,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        payload: dict[str, Any] = {}
        for line in reversed(cp.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    pass

        running = runner_running()
        result = {
            "ok": bool(running),
            "state": "runtime_active" if running else "runner_not_running",
            "host": host,
            "runner_home": str(runner),
            "runner_version": RUNNER_VERSION,
            "runner_registered_now": registration_performed,
            "runner_running": running,
            "watchdog_exit_code": cp.returncode,
            "watchdog_runtime_ok": bool(payload.get("runtime_ok")),
            "watchdog_activation_pending": bool(payload.get("activation_pending")),
            "watchdog_task": payload.get("task"),
            "source_sha": source_sha,
            "rdc_required": False,
            "production_touched": False,
            "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
            "registration_token_persisted": False,
            "registration_token_logged": False,
        }
        emit(result)
        return 0 if running else 3
    except ActivationError as exc:
        emit({
            "ok": False,
            "state": exc.state,
            "error": str(exc)[:1000],
            "rdc_required": False,
            "production_touched": False,
            "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
            "registration_token_persisted": False,
            "registration_token_logged": False,
        })
        return 4
    except Exception as exc:
        emit({
            "ok": False,
            "state": "unexpected_error",
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "rdc_required": False,
            "production_touched": False,
            "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
            "registration_token_persisted": False,
            "registration_token_logged": False,
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
