#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
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
HEADLESS_RUNNER_NAME = "NoteriHeadless"
HEADLESS_RUNNER_LABELS = "noteri-headless,reqsys-dev"
HEADLESS_RUNNER_HOME = Path(r"C:\actions-runner-noteri-headless")
EXPECTED_GITHUB_LOGIN = "ericson-j-santos"
SERVICE_NAME_RE = re.compile(r"^actions\.runner\.[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+$")

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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


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


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def runner_binary_contract(root: Path) -> bool:
    return (
        root.is_dir()
        and (root / "config.cmd").is_file()
        and (root / "run.cmd").is_file()
        and (root / "bin" / "Runner.Listener.exe").is_file()
    )


def service_runner_binary_contract(root: Path) -> bool:
    return runner_binary_contract(root) and (root / "bin" / "RunnerService.exe").is_file()


def runner_contract(root: Path) -> bool:
    return runner_binary_contract(root) and (root / ".runner").is_file()


def service_name(root: Path) -> str:
    marker = root / ".service"
    if not marker.is_file():
        return ""
    value = marker.read_text(encoding="utf-8", errors="replace").strip()
    if not SERVICE_NAME_RE.fullmatch(value):
        raise ActivationError("runner_service_marker_invalid", "marcador .service inválido")
    return value


def sc_path() -> Path:
    target = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "sc.exe"
    if not target.is_file():
        raise ActivationError("sc_missing", "sc.exe não encontrado")
    return target


def service_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    name = service_name(root)
    if not name:
        return {
            "exists": False,
            "running": False,
            "auto_start": False,
            "runner_home": str(root),
        }
    query = subprocess.run(
        [str(sc_path()), "query", name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    qc = subprocess.run(
        [str(sc_path()), "qc", name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    query_text = (query.stdout + "\n" + query.stderr).upper()
    qc_text = (qc.stdout + "\n" + qc.stderr).upper()
    exists = query.returncode == 0 and qc.returncode == 0
    running = exists and "RUNNING" in query_text
    auto_start = exists and "AUTO_START" in qc_text
    return {
        "exists": exists,
        "running": running,
        "auto_start": auto_start,
        "runner_home": str(root),
        "service_name": name,
        "validator": "windows_scm",
    }


def service_ready(status: dict[str, Any]) -> bool:
    return (
        status.get("exists") is True
        and status.get("running") is True
        and status.get("auto_start") is True
    )


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


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


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


def register_runner(
    root: Path,
    gh: Path,
    *,
    runner_name: str = RUNNER_NAME,
    runner_labels: str = RUNNER_LABELS,
    run_as_service: bool = False,
) -> bool:
    if runner_contract(root):
        if run_as_service and not (root / ".service").is_file():
            raise ActivationError(
                "runner_service_inconsistent",
                "runner headless já registrado sem marcador de serviço; não reconfigurar automaticamente",
            )
        return False
    if run_as_service and not is_admin():
        raise ActivationError("administrator_required", "registro como serviço Windows exige elevação administrativa")
    token = registration_token(gh)
    try:
        command = [
            str(root / "config.cmd"),
            "--unattended",
            "--url", REPOSITORY_URL,
            "--token", token,
            "--name", runner_name,
            "--labels", runner_labels,
            "--work", "_work",
            "--replace",
        ]
        if run_as_service:
            # O runner oficial escolhe NetworkService por padrão no Windows.
            # Não passamos usuário/senha para evitar dependência de conta localizada ou segredo.
            command.append("--runasservice")
        cp = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if cp.returncode != 0:
            raise ActivationError("runner_registration_failed", "registro do runner falhou")
    finally:
        token = ""
    if not runner_contract(root):
        raise ActivationError("runner_registration_failed", "contrato local do runner não foi criado")
    if run_as_service and not (root / ".service").is_file():
        raise ActivationError("runner_service_registration_failed", "runner não criou marcador .service")
    return True


def provision_runner(explicit: Path | None) -> tuple[Path, bool]:
    gh = ensure_gh()
    ensure_gh_auth(gh)
    root = explicit.resolve() if explicit else default_runner_home().resolve()
    ensure_runner_binaries(root)
    registered = register_runner(root, gh)
    return root, registered


def provision_headless_service_runner(explicit: Path | None) -> tuple[Path, bool, dict[str, Any]]:
    if not is_admin():
        raise ActivationError("administrator_required", "serviço headless exige elevação administrativa")
    gh = ensure_gh()
    ensure_gh_auth(gh)
    root = (explicit or HEADLESS_RUNNER_HOME).resolve()
    ensure_runner_binaries(root)
    if not service_runner_binary_contract(root):
        raise ActivationError("runner_service_binary_missing", "RunnerService.exe ausente no pacote oficial")
    registered = register_runner(
        root,
        gh,
        runner_name=HEADLESS_RUNNER_NAME,
        runner_labels=HEADLESS_RUNNER_LABELS,
        run_as_service=True,
    )
    status = service_status(root)
    return root, registered, status


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


def resolve_source_sha(repo_root: Path, supplied: str | None) -> str:
    value = (supplied or "").strip()
    if not value:
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
        value = cp.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ActivationError("source_sha_invalid", "source_sha inválido")
    return value.lower()


def finish(payload: dict[str, Any], code: int, result_path: Path | None) -> int:
    if result_path is not None:
        atomic_json(result_path.resolve(), payload)
    emit(payload)
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-sha")
    parser.add_argument("--runner-home", type=Path)
    parser.add_argument(
        "--mode",
        choices=("interactive", "headless-service", "headless-service-status"),
        default="interactive",
    )
    parser.add_argument("--result-path", type=Path)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        return finish({"ok": False, "state": "confirmation_invalid"}, 2, args.result_path)

    registration_performed = False
    registration_token_consumed_in_memory = False
    try:
        host = validate_host()
        repo_root = args.repo_root.resolve()
        source_sha = resolve_source_sha(repo_root, args.source_sha)

        if args.mode == "headless-service-status":
            root = (args.runner_home or HEADLESS_RUNNER_HOME).resolve()
            status = service_status(root)
            ready = service_ready(status)
            return finish(
                {
                    "ok": ready,
                    "state": "headless_service_active" if ready else "headless_service_not_ready",
                    "host": host,
                    "runner_name": HEADLESS_RUNNER_NAME,
                    "runner_labels": HEADLESS_RUNNER_LABELS.split(","),
                    "service": status,
                    "source_sha": source_sha,
                    "rdc_required": False,
                    "production_touched": False,
                    "secrets_read": False,
                    "registration_token_persisted": False,
                    "registration_token_logged": False,
                },
                0 if ready else 3,
                args.result_path,
            )

        if args.mode == "headless-service":
            root, registration_performed, status = provision_headless_service_runner(args.runner_home)
            registration_token_consumed_in_memory = registration_performed
            ready = service_ready(status)
            return finish(
                {
                    "ok": ready,
                    "state": "headless_service_active" if ready else "headless_service_not_ready",
                    "host": host,
                    "runner_home": str(root),
                    "runner_name": HEADLESS_RUNNER_NAME,
                    "runner_labels": HEADLESS_RUNNER_LABELS.split(","),
                    "runner_registered_now": registration_performed,
                    "service": status,
                    "source_sha": source_sha,
                    "rdc_required": False,
                    "production_touched": False,
                    "secrets_read": False,
                    "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
                    "registration_token_persisted": False,
                    "registration_token_logged": False,
                },
                0 if ready else 3,
                args.result_path,
            )

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
        return finish(result, 0 if running else 3, args.result_path)
    except ActivationError as exc:
        return finish(
            {
                "ok": False,
                "state": exc.state,
                "error": str(exc)[:1000],
                "rdc_required": False,
                "production_touched": False,
                "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
                "registration_token_persisted": False,
                "registration_token_logged": False,
            },
            4,
            args.result_path,
        )
    except Exception as exc:
        return finish(
            {
                "ok": False,
                "state": "unexpected_error",
                "error": str(exc)[:1000],
                "error_type": type(exc).__name__,
                "rdc_required": False,
                "production_touched": False,
                "registration_token_consumed_in_memory": registration_token_consumed_in_memory,
                "registration_token_persisted": False,
                "registration_token_logged": False,
            },
            2,
            args.result_path,
        )


if __name__ == "__main__":
    raise SystemExit(main())
