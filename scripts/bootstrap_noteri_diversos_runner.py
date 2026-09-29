#!/usr/bin/env python3
"""Bootstrap idempotente de runner self-hosted do repositório diversos no Noteri."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

try:
    import winreg
except ModuleNotFoundError:  # pragma: no cover - Windows only
    winreg = None

EXPECTED_HOST = "Noteri"
EXPECTED_GITHUB_LOGIN = "ericson-j-santos"
REPOSITORY = "ericson-j-santos/diversos"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
RUNNER_VERSION = "2.337.0"
RUNNER_NAME = "Noteri-diversos"
CUSTOM_LABELS = ("noteri", "diversos-dev")
REQUIRED_LABELS = ("self-hosted", "Windows", "X64", *CUSTOM_LABELS)
RUNNER_ASSET_URL = (
    "https://github.com/actions/runner/releases/download/"
    f"v{RUNNER_VERSION}/actions-runner-win-x64-{RUNNER_VERSION}.zip"
)
RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"
AUTHORIZATION_REF = "chat-20260928-diversos-noteri-dev"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "NoteriDiversosGitHubRunner"
CONFIRM = "BOOTSTRAP-NOTERI-DIVERSOS-RUNNER"
EVIDENCE_RESULT = "NOTERI_DIVERSOS_RUNNER_READY"


class BootstrapError(RuntimeError):
    pass


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def validate_context(*, host: str | None = None, os_name: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_os = os_name or os.name
    if actual_os != "nt":
        raise BootstrapError("windows_required")
    if actual_host.casefold() != EXPECTED_HOST.casefold():
        raise BootstrapError(f"host_not_allowed:{actual_host}")
    if platform.machine().casefold() not in {"amd64", "x86_64"}:
        raise BootstrapError("x64_required")


def default_runner_home() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise BootstrapError("localappdata_missing")
    return Path(local) / "ReqSys" / "NoteriDiversosGitHubRunner"


def stable_python_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise BootstrapError("localappdata_missing")
    return Path(local) / "ReqSys" / "PortablePython" / "3.12.10" / "python.exe"


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def find_gh() -> Path:
    located = shutil.which("gh")
    if located:
        return Path(located)
    candidates = (
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "GitHub CLI" / "gh.exe",
    )
    for item in candidates:
        if item.is_file():
            return item
    raise BootstrapError("github_cli_missing")


def gh_json(gh: Path, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [str(gh), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=False,
        env=gh_env(),
    )
    if completed.returncode != 0:
        raise BootstrapError("github_api_failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BootstrapError("github_api_invalid_json") from exc
    if not isinstance(payload, dict):
        raise BootstrapError("github_api_invalid_payload")
    return payload


def validate_gh_auth(gh: Path) -> None:
    completed = subprocess.run(
        [str(gh), "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=gh_env(),
    )
    if completed.returncode != 0:
        raise BootstrapError("github_auth_required")
    if completed.stdout.strip().casefold() != EXPECTED_GITHUB_LOGIN.casefold():
        raise BootstrapError("github_account_mismatch")


def request_registration_token(gh: Path) -> str:
    completed = subprocess.run(
        [
            str(gh), "api", "--method", "POST",
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
    token = completed.stdout.strip()
    if completed.returncode != 0 or len(token) < 20:
        raise BootstrapError("github_runner_admin_permission_required")
    return token


def runner_binary_contract(root: Path) -> bool:
    return (
        root.is_dir()
        and (root / "config.cmd").is_file()
        and (root / "run.cmd").is_file()
        and (root / "bin" / "Runner.Listener.exe").is_file()
    )


def runner_config_matches(root: Path) -> bool:
    path = root / ".runner"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("runner_config_invalid") from exc
    lowered = {str(key).casefold(): value for key, value in data.items()}
    url = str(lowered.get("githuburl") or "").rstrip("/")
    name = str(lowered.get("agentname") or "")
    if not url or not name:
        raise BootstrapError("runner_config_identity_missing")
    if url.casefold() != REPOSITORY_URL.casefold():
        raise BootstrapError("runner_registered_to_other_repository")
    if name.casefold() != RUNNER_NAME.casefold():
        raise BootstrapError("runner_name_mismatch")
    return True


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
            if destination != root and root not in destination.parents:
                raise BootstrapError("runner_archive_path_invalid")
        archive.extractall(target)


def ensure_runner_binaries(root: Path) -> bool:
    if runner_binary_contract(root):
        return False
    if root.exists() and any(root.iterdir()):
        raise BootstrapError("runner_home_nonempty_without_contract")
    root.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        RUNNER_ASSET_URL,
        headers={"User-Agent": "ReqSys-Noteri-Diversos-Runner/1.0"},
    )
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        archive = Path(handle.name)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if sha256_file(archive).casefold() != RUNNER_ASSET_SHA256.casefold():
            raise BootstrapError("runner_asset_sha256_mismatch")
        safe_extract(archive, root)
    finally:
        archive.unlink(missing_ok=True)
    if not runner_binary_contract(root):
        raise BootstrapError("runner_install_incomplete")
    return True


def _run_config(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    comspec = Path(os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe")
    if not comspec.is_file():
        raise BootstrapError("cmd_missing")
    return subprocess.run(
        [str(comspec), "/d", "/s", "/c", subprocess.list2cmdline([str(root / "config.cmd"), *args])],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=150,
        check=False,
        env=gh_env(),
    )


def ensure_registration(root: Path, gh: Path) -> bool:
    if (root / ".runner").is_file():
        if not runner_config_matches(root):
            raise BootstrapError("runner_config_missing_identity")
        return False
    token = request_registration_token(gh)
    try:
        completed = _run_config(
            root,
            [
                "--unattended",
                "--url", REPOSITORY_URL,
                "--token", token,
                "--name", RUNNER_NAME,
                "--labels", ",".join(CUSTOM_LABELS),
                "--work", "_work",
                "--replace",
            ],
        )
    finally:
        token = ""
    if completed.returncode != 0 or not runner_config_matches(root):
        raise BootstrapError("runner_registration_failed")
    return True


def startup_command(root: Path) -> str:
    comspec = Path(os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe")
    return subprocess.list2cmdline([str(comspec), "/d", "/c", str(root / "run.cmd")])


def ensure_startup(root: Path) -> bool:
    if winreg is None:
        raise BootstrapError("winreg_unavailable")
    expected = startup_command(root)
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_READ | winreg.KEY_SET_VALUE,
    ) as key:
        try:
            current, _ = winreg.QueryValueEx(key, RUN_VALUE)
        except FileNotFoundError:
            current = ""
        if str(current) == expected:
            return False
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, expected)
    return True


def runner_snapshot(gh: Path) -> dict[str, Any]:
    payload = gh_json(gh, ["api", f"repos/{REPOSITORY}/actions/runners?per_page=100"])
    raw = payload.get("runners")
    if not isinstance(raw, list):
        raise BootstrapError("runner_registry_invalid")
    matches = [
        item for item in raw
        if isinstance(item, dict)
        and str(item.get("name") or "").casefold() == RUNNER_NAME.casefold()
    ]
    if not matches:
        return {"present": False, "online": False, "busy": False, "labels": []}
    if len(matches) != 1:
        raise BootstrapError("runner_registry_ambiguous")
    item = matches[0]
    labels = sorted(
        str(label.get("name") or "")
        for label in (item.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    )
    return {
        "present": True,
        "online": str(item.get("status") or "").casefold() == "online",
        "busy": bool(item.get("busy")),
        "labels": labels,
    }


def labels_ok(labels: list[str]) -> bool:
    observed = {value.casefold() for value in labels}
    return {value.casefold() for value in REQUIRED_LABELS}.issubset(observed)


def start_listener(root: Path, gh: Path) -> bool:
    before = runner_snapshot(gh)
    if before["present"] and before["online"] and labels_ok(before["labels"]):
        return False
    env = os.environ.copy()
    env.pop("RUNNER_TRACKING_ID", None)
    py_dir = str(stable_python_path().parent)
    env["PATH"] = py_dir + os.pathsep + env.get("PATH", "")
    comspec = Path(os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe")
    subprocess.Popen(
        [str(comspec), "/d", "/c", str(root / "run.cmd")],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        close_fds=True,
        env=env,
    )
    return True


def wait_online(gh: Path, timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = runner_snapshot(gh)
    while time.monotonic() < deadline:
        if last["present"] and last["online"] and labels_ok(last["labels"]):
            return last
        time.sleep(2)
        last = runner_snapshot(gh)
    raise BootstrapError("runner_online_readback_timeout")


def provision_once(root: Path, gh: Path) -> dict[str, Any]:
    binaries_created = ensure_runner_binaries(root)
    registration_performed = ensure_registration(root, gh)
    startup_updated = ensure_startup(root)
    before = runner_snapshot(gh)
    listener_started = False
    if not (before["present"] and before["online"] and labels_ok(before["labels"])):
        listener_started = start_listener(root, gh)
    after = wait_online(gh)
    return {
        "binaries_created": binaries_created,
        "registration_performed": registration_performed,
        "startup_updated": startup_updated,
        "listener_started": listener_started,
        "registry": after,
        "mutated": any((binaries_created, registration_performed, startup_updated, listener_started)),
    }


def execute(*, confirm: str, authorization_ref: str, evidence_file: Path) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise BootstrapError("confirmation_invalid")
    if authorization_ref != AUTHORIZATION_REF:
        raise BootstrapError("authorization_ref_invalid")
    validate_context()
    if not stable_python_path().is_file():
        raise BootstrapError("stable_portable_python_missing")
    gh = find_gh()
    validate_gh_auth(gh)
    root = default_runner_home()
    first = provision_once(root, gh)
    replay = provision_once(root, gh)
    replay_idempotent = (
        replay["mutated"] is False
        and replay["registry"]["present"]
        and replay["registry"]["online"]
        and labels_ok(replay["registry"]["labels"])
    )
    if not replay_idempotent:
        raise BootstrapError("runner_replay_not_idempotent")
    evidence = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "result": EVIDENCE_RESULT,
        "environment": "dev",
        "host": EXPECTED_HOST,
        "repository": REPOSITORY,
        "runner_name": RUNNER_NAME,
        "runner_version": RUNNER_VERSION,
        "required_labels": list(REQUIRED_LABELS),
        "first": first,
        "replay": replay,
        "replay_idempotent": True,
        "authorization_ref": AUTHORIZATION_REF,
        "registration_token_consumed_in_memory": bool(first["registration_performed"]),
        "registration_token_persisted": False,
        "registration_token_logged": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--authorization-ref", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(
            confirm=args.confirm,
            authorization_ref=args.authorization_ref,
            evidence_file=args.evidence_file.resolve(),
        )
    except (BootstrapError, OSError, ValueError) as exc:
        safe = {
            "ok": False,
            "result": "NOTERI_DIVERSOS_RUNNER_BLOCKED",
            "reason": str(exc)[:300],
            "environment": "dev",
            "host": EXPECTED_HOST,
            "repository": REPOSITORY,
            "runner_name": RUNNER_NAME,
            "authorization_ref": AUTHORIZATION_REF,
            "registration_token_persisted": False,
            "registration_token_logged": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        args.evidence_file.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.resolve().write_text(
            json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
