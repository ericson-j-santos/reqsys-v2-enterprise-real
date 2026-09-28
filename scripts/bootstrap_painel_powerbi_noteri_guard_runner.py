#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_HOST = "NOTERI"
TARGET_REPO = "ericson-j-santos/painel-powerbi"
TARGET_URL = f"https://github.com/{TARGET_REPO}"
RUNNER_NAME = "Noteri-PainelPowerBI-Guard"
RUNNER_LABELS = ["noteri", "reqsys-dev", "painel-powerbi"]
CONFIRM = "REGISTER-PAINEL-POWERBI-NOTERI-GUARD-RUNNER"

RUNNER_VERSION = "2.337.0"
RUNNER_ASSET_URL = (
    "https://github.com/actions/runner/releases/download/"
    f"v{RUNNER_VERSION}/actions-runner-win-x64-{RUNNER_VERSION}.zip"
)
RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"


class BootstrapError(RuntimeError):
    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("RUNNER_TRACKING_ID", None)
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def validate_host() -> str:
    if os.name != "nt":
        raise BootstrapError("windows_required", "Windows obrigatório")
    host = platform.node().strip()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise BootstrapError("host_not_authorized", f"host não autorizado: {host}")
    return host


def find_gh() -> str:
    gh = shutil.which("gh")
    if not gh:
        raise BootstrapError("github_cli_required", "GitHub CLI ausente")
    return gh


def gh(args: list[str], *, timeout: int = 45) -> str:
    proc = subprocess.run(
        [find_gh(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=gh_env(),
    )
    if proc.returncode != 0:
        raise BootstrapError("github_api_failed", f"gh falhou: {args[0]}")
    return proc.stdout.strip()


def runner_home() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise BootstrapError("localappdata_missing", "LOCALAPPDATA não definido")
    return Path(local) / "PainelPowerBI" / "NoteriGitHubRunnerGuard"


def binary_contract(root: Path) -> bool:
    return (
        (root / "config.cmd").is_file()
        and (root / "run.cmd").is_file()
        and (root / "bin" / "Runner.Listener.exe").is_file()
    )


def local_contract(root: Path) -> bool:
    return binary_contract(root) and (root / ".runner").is_file()


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
                raise BootstrapError("runner_archive_invalid", "caminho inválido no ZIP")
        archive.extractall(target)


def ensure_binaries(root: Path) -> None:
    if binary_contract(root):
        return
    if root.exists() and any(root.iterdir()):
        raise BootstrapError("runner_home_not_empty", "runner home parcial/não vazio")
    root.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        RUNNER_ASSET_URL,
        headers={"User-Agent": "ReqSys-PainelPowerBI-Runner-Bootstrap/1.0"},
    )
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        archive = Path(handle.name)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, archive.open("wb") as out:
            shutil.copyfileobj(resp, out)
        if sha256_file(archive).casefold() != RUNNER_ASSET_SHA256.casefold():
            raise BootstrapError("runner_digest_mismatch", "SHA-256 do runner divergente")
        safe_extract(archive, root)
    finally:
        archive.unlink(missing_ok=True)
    if not binary_contract(root):
        raise BootstrapError("runner_install_incomplete", "binários incompletos")


def registry() -> dict[str, Any] | None:
    raw = gh(["api", f"repos/{TARGET_REPO}/actions/runners?per_page=100"])
    payload = json.loads(raw or "{}")
    for item in payload.get("runners", []):
        if str(item.get("name") or "") == RUNNER_NAME:
            return item
    return None


def labels_ok(item: dict[str, Any]) -> bool:
    observed = {str(x.get("name") or "") for x in item.get("labels", [])}
    return {"self-hosted", "Windows", "X64", *RUNNER_LABELS}.issubset(observed)


def request_registration_token() -> str:
    token = gh([
        "api",
        "--method",
        "POST",
        f"repos/{TARGET_REPO}/actions/runners/registration-token",
        "--jq",
        ".token",
    ])
    if len(token) < 20:
        raise BootstrapError("registration_token_unavailable", "token de registro inválido")
    return token


def register(root: Path) -> bool:
    current = registry()
    if current and str(current.get("status") or "") == "online" and labels_ok(current):
        return False
    if local_contract(root):
        if current is None:
            raise BootstrapError(
                "stale_local_registration",
                "runner local configurado sem registro GitHub correspondente",
            )
        return False

    token = request_registration_token()
    try:
        proc = subprocess.run(
            [
                str(root / "config.cmd"),
                "--unattended",
                "--url",
                TARGET_URL,
                "--token",
                token,
                "--name",
                RUNNER_NAME,
                "--labels",
                ",".join(RUNNER_LABELS),
                "--work",
                "_work",
                "--replace",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
            env=child_env(),
        )
        if proc.returncode != 0:
            raise BootstrapError("runner_registration_failed", "config.cmd falhou")
    finally:
        token = ""
    if not local_contract(root):
        raise BootstrapError("runner_registration_failed", "contrato local não criado")
    return True


def start_runner(root: Path) -> None:
    comspec = Path(os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe")
    if not comspec.is_file():
        raise BootstrapError("cmd_missing", "cmd.exe não encontrado")
    subprocess.Popen(
        [str(comspec), "/d", "/c", str(root / "run.cmd")],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        close_fds=True,
        env=child_env(),
    )


def wait_online(timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last = registry()
        if (
            last
            and str(last.get("status") or "") == "online"
            and labels_ok(last)
        ):
            return last
        time.sleep(2)
    raise BootstrapError(
        "runner_not_online",
        f"runner não ficou online; last_status={str((last or {}).get('status') or 'missing')}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        emit({"ok": False, "state": "confirmation_invalid"})
        return 2
    if len(args.source_sha.strip()) != 40:
        emit({"ok": False, "state": "source_sha_invalid"})
        return 2

    registered_now = False
    try:
        host = validate_host()
        login = gh(["api", "user", "--jq", ".login"])
        if login.casefold() != "ericson-j-santos":
            raise BootstrapError("github_account_mismatch", "conta GitHub local divergente")
        gh(["repo", "view", TARGET_REPO, "--json", "nameWithOwner"])

        root = runner_home()
        ensure_binaries(root)
        registered_now = register(root)

        current = registry()
        if not (
            current
            and str(current.get("status") or "") == "online"
            and labels_ok(current)
        ):
            start_runner(root)
            current = wait_online()

        emit(
            {
                "ok": True,
                "state": "runner_online",
                "host": host,
                "target_repo": TARGET_REPO,
                "runner_name": RUNNER_NAME,
                "runner_labels_ok": labels_ok(current),
                "runner_status": current.get("status"),
                "runner_busy": bool(current.get("busy")),
                "runner_registered_now": registered_now,
                "runner_home": str(root),
                "source_sha": args.source_sha.strip().lower(),
                "registration_token_persisted": False,
                "registration_token_logged": False,
                "production_touched": False,
                "rdc_required": False,
            }
        )
        return 0
    except BootstrapError as exc:
        emit(
            {
                "ok": False,
                "state": exc.state,
                "error": str(exc)[:500],
                "target_repo": TARGET_REPO,
                "runner_name": RUNNER_NAME,
                "runner_registered_now": registered_now,
                "registration_token_persisted": False,
                "registration_token_logged": False,
                "production_touched": False,
                "rdc_required": False,
            }
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
