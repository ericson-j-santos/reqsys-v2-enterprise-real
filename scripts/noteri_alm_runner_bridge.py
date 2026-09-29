#!/usr/bin/env python3
"""Ponte efêmera e governada do Noteri para CI do reqsys-powerplatform-alm PR #7."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
EXPECTED_LOGIN = "ericson-j-santos"
TARGET_REPOSITORY = "ericson-j-santos/reqsys-powerplatform-alm"
TARGET_REPOSITORY_URL = f"https://github.com/{TARGET_REPOSITORY}"
TARGET_PR = 7
TARGET_BRANCH = "diag/outlook-connection-probe-20260928"
REQUIRED_WORKFLOWS = (
    "Build and Deploy to Test",
    "Power Platform Outlook Connection Read-only Probe",
)
RUNNER_VERSION = "2.337.0"
RUNNER_ASSET_URL = (
    "https://github.com/actions/runner/releases/download/"
    f"v{RUNNER_VERSION}/actions-runner-win-x64-{RUNNER_VERSION}.zip"
)
RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"
RUNNER_LABELS = "noteri,reqsys-dev,alm-pr7"
RUNNER_SLOTS = 2
POLL_SECONDS = 10
TIMEOUT_SECONDS = 900


class BridgeError(RuntimeError):
    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def _find_gh() -> Path:
    found = shutil.which("gh")
    candidates = [
        Path(found) if found else None,
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "GitHub CLI" / "gh.exe",
    ]
    for item in candidates:
        if item and item.is_file():
            return item
    raise BridgeError("github_cli_missing", "GitHub CLI não encontrado")


def _run_gh(gh: Path, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(gh), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_gh_env(),
    )


def _gh_json(gh: Path, endpoint: str) -> dict[str, Any]:
    cp = _run_gh(gh, ["api", endpoint])
    if cp.returncode != 0:
        raise BridgeError("github_api_failed", f"GitHub API falhou para endpoint governado: {endpoint.split('?')[0]}")
    try:
        value = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError("github_api_invalid_json", "GitHub API retornou JSON inválido") from exc
    if not isinstance(value, dict):
        raise BridgeError("github_api_invalid_shape", "GitHub API retornou formato inesperado")
    return value


def _validate_host() -> str:
    if os.name != "nt":
        raise BridgeError("windows_required", "Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise BridgeError("host_mismatch", f"host inesperado: {host}")
    if platform.machine().casefold() not in {"amd64", "x86_64"}:
        raise BridgeError("x64_required", "arquitetura x64 obrigatória")
    return host


def _validate_identity(gh: Path) -> None:
    cp = _run_gh(gh, ["api", "user", "--jq", ".login"])
    if cp.returncode != 0 or cp.stdout.strip().casefold() != EXPECTED_LOGIN.casefold():
        raise BridgeError("github_identity_mismatch", "perfil local gh não pertence ao owner esperado")


def _pr_target(gh: Path) -> str:
    payload = _gh_json(gh, f"repos/{TARGET_REPOSITORY}/pulls/{TARGET_PR}")
    if payload.get("state") != "open":
        raise BridgeError("target_pr_not_open", "PR #7 precisa permanecer aberta durante a execução")
    if str((payload.get("base") or {}).get("ref") or "") != "main":
        raise BridgeError("target_base_mismatch", "PR #7 não aponta para main")
    head = payload.get("head") or {}
    if str(head.get("ref") or "") != TARGET_BRANCH:
        raise BridgeError("target_branch_mismatch", "branch do PR #7 divergiu do alvo governado")
    if str((head.get("repo") or {}).get("full_name") or "") != TARGET_REPOSITORY:
        raise BridgeError("target_repository_mismatch", "repositório head do PR #7 divergiu do alvo governado")
    sha = str(head.get("sha") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise BridgeError("target_pr_head_invalid", "HEAD atual do PR #7 é inválido")
    return sha


def _workflow_state(gh: Path, expected_head: str) -> dict[str, dict[str, Any]]:
    payload = _gh_json(
        gh,
        f"repos/{TARGET_REPOSITORY}/actions/runs?head_sha={expected_head}&per_page=100",
    )
    selected: dict[str, dict[str, Any]] = {}
    for item in payload.get("workflow_runs") or []:
        name = str(item.get("name") or "")
        if name not in REQUIRED_WORKFLOWS:
            continue
        current = selected.get(name)
        if current is None or int(item.get("id") or 0) > int(current.get("id") or 0):
            selected[name] = {
                "id": int(item.get("id") or 0),
                "status": str(item.get("status") or ""),
                "conclusion": item.get("conclusion"),
                "head_sha": str(item.get("head_sha") or "").lower(),
            }
    return selected


def _all_success(state: dict[str, dict[str, Any]], expected_head: str) -> bool:
    return all(
        state.get(name, {}).get("status") == "completed"
        and state.get(name, {}).get("conclusion") == "success"
        and state.get(name, {}).get("head_sha") == expected_head
        for name in REQUIRED_WORKFLOWS
    )


def _all_terminal(state: dict[str, dict[str, Any]]) -> bool:
    return all(state.get(name, {}).get("status") == "completed" for name in REQUIRED_WORKFLOWS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_runner(root: Path) -> Path:
    archive = root / f"actions-runner-{RUNNER_VERSION}.zip"
    request = urllib.request.Request(
        RUNNER_ASSET_URL,
        headers={"User-Agent": "ReqSys-Noteri-ALM-Runner-Bridge/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    if _sha256(archive).casefold() != RUNNER_ASSET_SHA256.casefold():
        raise BridgeError("runner_digest_mismatch", "SHA-256 do runner oficial divergiu")
    return archive


def _extract_runner(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    resolved = target.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            destination = (target / member.filename).resolve()
            if destination != resolved and resolved not in destination.parents:
                raise BridgeError("runner_archive_invalid", "arquivo do runner contém caminho inválido")
        zf.extractall(target)
    required = (target / "config.cmd", target / "bin" / "Runner.Listener.exe")
    if not all(item.is_file() for item in required):
        raise BridgeError("runner_install_incomplete", "binários oficiais do runner incompletos")


def _registration_token(gh: Path) -> str:
    cp = _run_gh(
        gh,
        [
            "api", "--method", "POST",
            f"repos/{TARGET_REPOSITORY}/actions/runners/registration-token",
            "--jq", ".token",
        ],
    )
    token = cp.stdout.strip()
    if cp.returncode != 0 or len(token) < 20:
        raise BridgeError("runner_admin_permission_required", "perfil local gh não autorizou registro do runner")
    return token


def _register_slot(gh: Path, archive: Path, root: Path, slot: int) -> tuple[Path, str]:
    home = root / f"slot-{slot}"
    _extract_runner(archive, home)
    token = _registration_token(gh)
    name = f"Noteri-ALM-PR7-{os.environ.get('GITHUB_RUN_ID', 'manual')}-{slot}"
    try:
        cp = subprocess.run(
            [
                str(home / "config.cmd"),
                "--unattended",
                "--url", TARGET_REPOSITORY_URL,
                "--token", token,
                "--name", name,
                "--labels", RUNNER_LABELS,
                "--work", "_work",
                "--ephemeral",
                "--disableupdate",
            ],
            cwd=home,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    finally:
        del token
    if cp.returncode != 0 or not (home / ".runner").is_file():
        raise BridgeError("runner_registration_failed", f"registro do slot {slot} falhou")
    return home, name


def _start_listener(home: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [str(home / "bin" / "Runner.Listener.exe"), "run"],
        cwd=home,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )


def _stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _resolve_evidence_path() -> Path:
    raw = (os.environ.get("REQSYS_ALM_RUNNER_EVIDENCE_FILE") or "").strip()
    temp_raw = (os.environ.get("RUNNER_TEMP") or "").strip()
    if not raw or not temp_raw:
        raise BridgeError("evidence_path_missing", "RUNNER_TEMP/evidence path ausente")
    path = Path(raw).resolve()
    temp_root = Path(temp_raw).resolve()
    if path.parent != temp_root or path.suffix.casefold() != ".json":
        raise BridgeError("evidence_path_invalid", "evidência deve permanecer diretamente em RUNNER_TEMP")
    return path


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    evidence: dict[str, Any] = {
        "schema": "reqsys-noteri-alm-runner-bridge/v1",
        "target_repository": TARGET_REPOSITORY,
        "target_pr": TARGET_PR,
        "production_touched": False,
        "secrets_read": False,
        "token_exposed": False,
        "registration_token_persisted": False,
        "registration_token_logged": False,
        "independent_readback": False,
        "replay_idempotent": False,
        "runner_slots": RUNNER_SLOTS,
    }
    processes: list[subprocess.Popen[bytes]] = []
    runtime_root: Path | None = None
    evidence_path: Path | None = None
    try:
        evidence_path = _resolve_evidence_path()
        evidence["host"] = _validate_host()
        gh = _find_gh()
        _validate_identity(gh)
        expected_head = _pr_target(gh)
        evidence["expected_head"] = expected_head
        evidence["target_branch"] = TARGET_BRANCH
        evidence["observed_head_before"] = expected_head

        initial = _workflow_state(gh, expected_head)
        evidence["workflow_state_before"] = initial
        if _all_success(initial, expected_head):
            evidence.update({
                "status": "ALREADY_COMPLIANT",
                "independent_readback": True,
                "replay_idempotent": True,
                "observed_head_after": expected_head,
                "workflow_state_after": initial,
            })
            _write_evidence(evidence_path, evidence)
            _emit({"ok": True, "status": "ALREADY_COMPLIANT"})
            return 0

        base = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        runtime_root = Path(tempfile.mkdtemp(prefix="reqsys-alm-bridge-", dir=str(base)))
        archive = _download_runner(runtime_root)
        names: list[str] = []
        for slot in range(1, RUNNER_SLOTS + 1):
            home, name = _register_slot(gh, archive, runtime_root, slot)
            names.append(name)
            processes.append(_start_listener(home))
        evidence["runner_names"] = names

        deadline = time.monotonic() + TIMEOUT_SECONDS
        final = initial
        while time.monotonic() < deadline:
            if _pr_target(gh) != expected_head:
                raise BridgeError("target_head_changed_during_run", "PR #7 mudou durante a execução")
            final = _workflow_state(gh, expected_head)
            if _all_terminal(final):
                break
            time.sleep(POLL_SECONDS)

        after = _pr_target(gh)
        evidence["observed_head_after"] = after
        evidence["workflow_state_after"] = final
        evidence["independent_readback"] = after == expected_head and _all_terminal(final)
        if after != expected_head:
            raise BridgeError("target_head_changed_after_run", "PR #7 mudou antes do readback final")
        if not _all_terminal(final):
            raise BridgeError("target_checks_timeout", "checks do PR #7 não chegaram a estado terminal")
        if not _all_success(final, expected_head):
            evidence["status"] = "TARGET_CHECK_FAILED"
            _write_evidence(evidence_path, evidence)
            _emit({"ok": False, "status": "TARGET_CHECK_FAILED"})
            return 6

        evidence["status"] = "READY"
        evidence["replay_idempotent"] = True
        _write_evidence(evidence_path, evidence)
        _emit({"ok": True, "status": "READY"})
        return 0
    except BridgeError as exc:
        evidence["status"] = "BLOCKED"
        evidence["reason"] = exc.state
        evidence["error"] = str(exc)[:500]
        if evidence_path is not None:
            _write_evidence(evidence_path, evidence)
        _emit({"ok": False, "status": "BLOCKED", "reason": exc.state})
        return 5
    except Exception as exc:
        evidence["status"] = "BLOCKED"
        evidence["reason"] = "unexpected_error"
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)[:500]
        if evidence_path is not None:
            _write_evidence(evidence_path, evidence)
        _emit({"ok": False, "status": "BLOCKED", "reason": "unexpected_error"})
        return 2
    finally:
        _stop_processes(processes)
        if runtime_root and runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
