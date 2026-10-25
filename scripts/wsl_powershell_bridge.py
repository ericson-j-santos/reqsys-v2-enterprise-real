#!/usr/bin/env python3
"""Ponte governada WSL -> Windows PowerShell para scripts versionados.

Não aceita código PowerShell inline, executável arbitrário nem shell=True. Cada
script e sua lista exata de argumentos devem existir na política versionada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "1"
DEFAULT_POLICY = Path("config/wsl-powershell-bridge.policy.json")
SECRET_NAME = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL|AUTH)",
    re.IGNORECASE,
)


class BridgeError(RuntimeError):
    """Falha fechada do transporte WSL -> PowerShell."""


def is_wsl(*, environ: Mapping[str, str] | None = None, release: str | None = None) -> bool:
    env = environ or os.environ
    kernel = (release if release is not None else platform.release()).casefold()
    return bool(env.get("WSL_INTEROP") or env.get("WSL_DISTRO_NAME") or "microsoft" in kernel)


def load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"policy_invalid:{type(exc).__name__}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BridgeError("policy_schema_invalid")
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        raise BridgeError("policy_scripts_invalid")
    return payload


def resolve_script(repo_root: Path, requested: Path) -> tuple[Path, str]:
    root = repo_root.resolve()
    script = requested if requested.is_absolute() else root / requested
    script = script.resolve()
    try:
        relative = script.relative_to(root).as_posix()
    except ValueError as exc:
        raise BridgeError("script_outside_repository") from exc
    if script.suffix.casefold() != ".ps1":
        raise BridgeError("script_extension_invalid")
    if not script.is_file():
        raise BridgeError("script_not_found")
    return script, relative


def validate_request(
    policy: Mapping[str, Any],
    *,
    repo_root: Path,
    requested_script: Path,
    script_args: Sequence[str],
    timeout_seconds: int,
) -> tuple[Path, str, dict[str, Any], int]:
    script, relative = resolve_script(repo_root, requested_script)
    rule = policy.get("scripts", {}).get(relative)
    if not isinstance(rule, dict):
        raise BridgeError("script_not_allowlisted")
    expected_args = rule.get("arguments")
    if not isinstance(expected_args, list) or any(not isinstance(item, str) for item in expected_args):
        raise BridgeError("policy_arguments_invalid")
    if list(script_args) != expected_args:
        raise BridgeError("script_arguments_not_allowlisted")
    maximum = int(policy.get("max_timeout_seconds", 300))
    if maximum < 1 or timeout_seconds < 1 or timeout_seconds > maximum:
        raise BridgeError("timeout_out_of_policy")
    if str(rule.get("environment", "")).casefold() not in {"local/dev", "dev"}:
        raise BridgeError("environment_not_dev")
    return script, relative, rule, timeout_seconds


def resolve_powershell() -> Path:
    candidates = [
        shutil.which("powershell.exe"),
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    for raw in candidates:
        if raw and Path(raw).is_file():
            return Path(raw)
    raise BridgeError("windows_powershell_not_found")


def windows_path(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["wslpath", "-w", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BridgeError("wslpath_failed") from exc
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value:
        raise BridgeError("wslpath_failed")
    return value


def sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(source or os.environ)
    for name in list(env):
        if name == "WSLENV" or SECRET_NAME.search(name):
            env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def build_command(executable: Path, windows_script: str, script_args: Sequence[str]) -> list[str]:
    return [
        str(executable),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        windows_script,
        *script_args,
    ]


def default_evidence_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return root / "reqsys" / "wsl-powershell-bridge" / f"{stamp}-{os.getpid()}.json"


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def execute(
    *,
    executable: Path,
    script: Path,
    relative_script: str,
    script_args: Sequence[str],
    timeout_seconds: int,
    evidence_path: Path,
    rule: Mapping[str, Any],
) -> int:
    command = build_command(executable, windows_path(script), script_args)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=sanitized_environment(),
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = int(completed.returncode)
        status = "completed" if exit_code == 0 else "command_failed"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code = 124
        status = "timeout"
    duration_ms = int((time.monotonic() - started) * 1000)
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "script": relative_script,
        "environment": rule.get("environment"),
        "interactive_uac": bool(rule.get("interactive_uac")),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8", errors="replace")).hexdigest(),
        "stderr_bytes": len(stderr.encode("utf-8", errors="replace")),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8", errors="replace")).hexdigest(),
        "secrets_logged": False,
        "production_touched": False,
    }
    atomic_json(evidence_path, evidence)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    print(json.dumps({"bridge_evidence": str(evidence_path), **evidence}, sort_keys=True), file=sys.stderr)
    return exit_code


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    result.add_argument("--policy", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("probe")
    run = commands.add_parser("run")
    run.add_argument("--script", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=int, default=180)
    run.add_argument("--evidence", type=Path)
    run.add_argument("script_args", nargs=argparse.REMAINDER)
    return result


def main() -> int:
    args = parser().parse_args()
    if not is_wsl():
        print(json.dumps({"status": "blocked", "reason_code": "wsl_required"}))
        return 2
    try:
        executable = resolve_powershell()
        if args.command == "probe":
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "powershell": str(executable),
                        "wsl_interop": True,
                        "production_touched": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        repo_root = args.repo_root.resolve()
        policy_path = (args.policy or (repo_root / DEFAULT_POLICY)).resolve()
        policy = load_policy(policy_path)
        script_args = list(args.script_args)
        if script_args[:1] == ["--"]:
            script_args = script_args[1:]
        script, relative, rule, timeout_seconds = validate_request(
            policy,
            repo_root=repo_root,
            requested_script=args.script,
            script_args=script_args,
            timeout_seconds=args.timeout_seconds,
        )
        return execute(
            executable=executable,
            script=script,
            relative_script=relative,
            script_args=script_args,
            timeout_seconds=timeout_seconds,
            evidence_path=(args.evidence or default_evidence_path()).resolve(),
            rule=rule,
        )
    except BridgeError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason_code": str(exc),
                    "production_touched": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
