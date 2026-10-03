#!/usr/bin/env python3
"""Two closed DEV owner actions. Never registers or broadens local grants."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import getpass
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

class OperationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

HOST = "DESKTOP-PDQK954"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
REMOTE = "https://github.com/" + REPOSITORY + ".git"
WORKERS = Path("C:/dev/chatgpt-workers")
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
LAUNCHER = "scripts/run_self_hosted_dev_owner_action.py"
SCRIPTS = {
    "recipient": "scripts/dev_backup_transport.py",
    "prepare": "scripts/reqsys_self_hosted_dev_publish.py",
}
ACTION_IDS = {
    "recipient": "reqsys.selfhost.receiver.init.dev",
    "prepare": "reqsys.selfhost.publisher.prepare.dev",
}
SCOPES = {
    "recipient": "repo://reqsys/environment/dev/migration/recipient",
    "prepare": "repo://reqsys/environment/dev/selfhost",
}

def require_hex(value, expression, code):
    if not isinstance(value, str) or not expression.fullmatch(value):
        raise OperationError(code)
    return value

def no_reparse(path):
    path = Path(path)
    for current in (path, *path.parents):
        info = current.lstat()
        if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OperationError("reparse_path_blocked")
    if path.is_file() and path.stat().st_nlink != 1:
        raise OperationError("hardlink_path_blocked")

def require_host():
    if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
        raise OperationError("fixed_windows_host_required")

def file_digest(path):
    no_reparse(path)
    if not path.is_file() or path.stat().st_size > 1048576:
        raise OperationError("script_size_or_type_invalid")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_root(expected_sha):
    require_hex(expected_sha, SHA, "invalid_source_sha")
    return WORKERS / ("rs2-" + expected_sha)

def git_read(root, args):
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    })
    result = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        shell=False, capture_output=True, text=True, encoding="utf-8",
        errors="strict", timeout=30, check=False, env=environment,
    )
    if result.returncode or result.stderr.strip() or len(result.stdout) > 2097152:
        raise OperationError("source_git_validation_failed")
    return result.stdout.rstrip("\r\n")

def validate_repository(root, expected_sha):
    no_reparse(root)
    if not root.is_dir():
        raise OperationError("source_root_missing")
    actual = Path(git_read(root, ["rev-parse", "--show-toplevel"])).resolve()
    if actual != root.resolve():
        raise OperationError("source_root_mismatch")
    if git_read(root, ["remote", "get-url", "origin"]) != REMOTE:
        raise OperationError("source_origin_mismatch")
    if git_read(root, ["rev-parse", "HEAD"]) != expected_sha:
        raise OperationError("source_head_mismatch")
    if git_read(root, ["status", "--porcelain", "--untracked-files=all"]):
        raise OperationError("source_tree_dirty")
    records = git_read(root, ["ls-files", "-v"]).splitlines()
    if not records or any(not row.startswith("H ") for row in records):
        raise OperationError("source_index_flags_untrusted")

def validate_scripts(root, script_digests):
    for relative, digest in script_digests.items():
        require_hex(digest, DIGEST, "invalid_script_sha256")
        if relative not in {*SCRIPTS.values(), LAUNCHER}:
            raise OperationError("script_not_closed")
        if git_read(root, ["ls-files", "--error-unmatch", relative]) != relative:
            raise OperationError("script_not_tracked")
        if file_digest(root / relative) != digest:
            raise OperationError("script_sha256_mismatch")

def python_executable():
    path = Path(sys.executable)
    if not path.is_absolute() or path.name.casefold() not in ("python.exe", "python3.exe"):
        raise OperationError("absolute_python_executable_required")
    no_reparse(path)
    if not path.is_file():
        raise OperationError("python_executable_missing")
    return str(path)

CONFIG_PATH = Path("C:/Users/Windows/AppData/Local/ReqSys/CommandGateway/owner-risk3-exceptions.local.json")
GRANT_CONTRACT = "reqsys-selfhost-dev-two-actions-one-hour-v1"


def validate_grant_payload(config, phase, expected_sha, script_sha256,
                           launcher_sha256, python, now, fingerprint):
    if phase not in SCRIPTS:
        raise OperationError("phase_not_closed")
    require_hex(expected_sha, SHA, "invalid_source_sha")
    require_hex(script_sha256, DIGEST, "invalid_script_sha256")
    require_hex(launcher_sha256, DIGEST, "invalid_launcher_sha256")
    root = source_root(expected_sha)
    if not isinstance(config, dict) or type(config.get("version")) is not int or config.get("version") != 1:
        raise OperationError("active_private_grant_required")
    if config.get("enabled") is not True or config.get("owner_fingerprint") != fingerprint:
        raise OperationError("private_grant_owner_or_enabled_mismatch")
    mode = config.get("development_mode")
    if "development_mode" in config and (not isinstance(mode, dict) or mode.get("enabled") is not False):
        raise OperationError("broad_development_mode_must_remain_disabled")
    actions = config.get("actions")
    grant = actions.get(ACTION_IDS[phase]) if isinstance(actions, dict) else None
    if not isinstance(grant, dict):
        raise OperationError("active_private_grant_required")
    expected_command = [
        python, str(root / LAUNCHER), phase,
        "--source-sha", expected_sha, "--script-sha256", script_sha256,
    ]
    try:
        start = datetime.fromisoformat(grant["valid_from"])
        expiry = datetime.fromisoformat(grant["expires_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OperationError("private_grant_window_invalid") from exc
    if (
        start.tzinfo is None or expiry.tzinfo is None
        or start.utcoffset() != timedelta(0) or expiry.utcoffset() != timedelta(0)
        or expiry - start != timedelta(hours=1)
        or start.minute or start.second or start.microsecond
        or not start <= now < expiry
    ):
        raise OperationError("private_grant_expired_or_window_invalid")
    expected = {
        "environment": "dev", "scope": SCOPES[phase],
        "valid_from": start.isoformat(), "expires_at": expiry.isoformat(),
        "command": expected_command, "grant_contract": GRANT_CONTRACT,
        "source_sha": expected_sha, "script_sha256": script_sha256,
        "launcher_sha256": launcher_sha256,
    }
    if grant != expected:
        raise OperationError("private_grant_binding_mismatch")

def validate_active_grant(root, phase, expected_sha, script_sha256, python):
    """An unregistered/direct call cannot grant itself permission."""
    no_reparse(CONFIG_PATH)
    if not CONFIG_PATH.is_file() or CONFIG_PATH.stat().st_size > 262144:
        raise OperationError("active_private_grant_required")
    publisher_path = root / SCRIPTS["prepare"]
    no_reparse(publisher_path)
    if git_read(root, ["ls-files", "--error-unmatch", SCRIPTS["prepare"]]) != SCRIPTS["prepare"]:
        raise OperationError("publisher_not_tracked")
    spec = importlib.util.spec_from_file_location("_approved_reqsys_dev_publisher", publisher_path)
    publisher = importlib.util.module_from_spec(spec)
    old_no_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(publisher)
    finally:
        sys.dont_write_bytecode = old_no_bytecode
    publisher.WindowsPrivateFiles().check(CONFIG_PATH)
    raw = CONFIG_PATH.read_bytes()
    if len(raw) > 262144:
        raise OperationError("private_grant_configuration_too_large")
    def strict_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise OperationError("private_grant_configuration_duplicate_key")
            obj[key] = value
        return obj
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
    fingerprint = hashlib.sha256(
        f"{getpass.getuser()}@{socket.gethostname()}".encode("utf-8", errors="replace")
    ).hexdigest()
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.GetUserNameW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    size = wintypes.DWORD(256)
    user = ctypes.create_unicode_buffer(size.value)
    if not adv.GetUserNameW(user, ctypes.byref(size)) or user.value.casefold() != "windows":
        raise OperationError("windows_owner_mismatch")
    if getpass.getuser().casefold() != "windows":
        raise OperationError("windows_owner_mismatch")
    validate_grant_payload(
        config, phase, expected_sha, script_sha256, file_digest(root / LAUNCHER),
        python, datetime.now(timezone.utc), fingerprint,
    )

def validate_execution(phase, expected_sha, script_sha256):
    if phase not in SCRIPTS:
        raise OperationError("phase_not_closed")
    require_host()
    root = source_root(expected_sha)
    if Path(__file__).resolve() != (root / LAUNCHER).resolve():
        raise OperationError("launcher_location_mismatch")
    validate_repository(root, expected_sha)
    validate_scripts(root, {SCRIPTS[phase]: script_sha256})
    if git_read(root, ["ls-files", "--error-unmatch", LAUNCHER]) != LAUNCHER:
        raise OperationError("launcher_not_tracked")
    no_reparse(root / LAUNCHER)
    no_reparse(Path.cwd())
    current = Path.cwd().resolve()
    if current != root.resolve():
        if current.parent != WORKERS.resolve() or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,160}", current.name
        ):
            raise OperationError("cwd_namespace_not_allowed")
        validate_repository(current, expected_sha)
    return root

def child_command(phase, root, expected_sha, python):
    if phase == "recipient":
        return [
            python, str(root / SCRIPTS[phase]), "recipient-init",
            "--confirm", "INIT-PC24X7-DEV-MIGRATION-IDENTITY",
        ]
    if phase == "prepare":
        return [
            python, str(root / SCRIPTS[phase]), "prepare",
            "--source-root", str(root), "--expected-sha", expected_sha,
            "--correlation-id", "pc24x7-owner-dev-" + expected_sha[:12],
        ]
    raise OperationError("phase_not_closed")

def execute(phase, expected_sha, script_sha256):
    root = validate_execution(phase, expected_sha, script_sha256)
    python = python_executable()
    validate_active_grant(root, phase, expected_sha, script_sha256, python)
    command = child_command(phase, root, expected_sha, python)
    completed = subprocess.run(
        command, cwd=str(root), shell=False, capture_output=True,
        timeout=120 if phase == "recipient" else 840, check=False,
    )
    if completed.returncode != 0:
        raise OperationError("closed_child_failed")
    return {
        "status": "completed", "phase": phase,
        "source_sha": expected_sha, "script_sha256": script_sha256,
        "development_mode_changed": False,
        "dev_pointer_changed": False, "usable": False,
    }

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=tuple(SCRIPTS))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--script-sha256", required=True)
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        evidence = execute(args.phase, args.source_sha, args.script_sha256)
    except Exception as exc:
        code = exc.code if isinstance(exc, OperationError) else "closed_action_failed"
        print(json.dumps({"status": "blocked", "code": code}, sort_keys=True))
        return 2
    print(json.dumps(evidence, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
