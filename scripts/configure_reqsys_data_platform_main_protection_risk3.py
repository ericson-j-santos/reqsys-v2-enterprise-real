#!/usr/bin/env python3
"""Instala uma excecao Owner Risk3 temporaria para proteger reqsys-data-platform/main."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ACTION_ID = "reqsys.data-platform-main-protection.dev"
SCOPE = "repo://ericson-j-santos/reqsys-data-platform/branch/main"
MANAGED_BY = "reqsys-data-platform-main-protection-once"
ENABLE_CONFIRM = "ENABLE-REQSYS-DATA-PLATFORM-MAIN-PROTECTION-ONCE"
DISABLE_CONFIRM = "DISABLE-REQSYS-DATA-PLATFORM-MAIN-PROTECTION-ONCE"
EVIDENCE_PATH = "artifacts/reqsys-data-platform-main-protection-noteri/evidence.json"
COMMAND = [
    "python",
    "scripts/run_reqsys_data_platform_main_protection_local.py",
    "--output",
    EVIDENCE_PATH,
]
DEFAULT_TTL_MINUTES = 30


class ConfigError(RuntimeError):
    pass


def owner_fingerprint() -> str:
    identity = f"{getpass.getuser()}@{socket.gethostname()}".encode("utf-8", errors="replace")
    return hashlib.sha256(identity).hexdigest()


def default_config_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "ReqSys" / "CommandGateway" / "owner-risk3-exceptions.local.json"
    return Path.home() / ".reqsys-command-gateway" / "owner-risk3-exceptions.local.json"


def _load(path: Path) -> dict:
    if not path.is_absolute() or path.name != "owner-risk3-exceptions.local.json":
        raise ConfigError("risk3_config_path_invalid")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError("risk3_config_invalid") from exc
        if data.get("version") != 1:
            raise ConfigError("risk3_config_version_invalid")
        if data.get("owner_fingerprint") != owner_fingerprint():
            raise ConfigError("risk3_config_owner_mismatch")
    else:
        data = {
            "version": 1,
            "enabled": True,
            "owner_fingerprint": owner_fingerprint(),
            "actions": {},
        }
    data["enabled"] = True
    if not isinstance(data.get("actions"), dict):
        data["actions"] = {}
    return data


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="risk3-action-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        if os.name != "nt":
            os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def enable(path: Path, ttl_minutes: int) -> dict:
    if ttl_minutes < 1 or ttl_minutes > 60:
        raise ConfigError("ttl_minutes_out_of_range")
    data = _load(path)
    existing = data["actions"].get(ACTION_ID)
    if isinstance(existing, dict) and existing.get("managed_by") != MANAGED_BY:
        same = (
            existing.get("environment") == "dev"
            and existing.get("scope") == SCOPE
            and existing.get("command") == COMMAND
        )
        if not same:
            raise ConfigError("risk3_action_conflict")
        return {"status": "existing_exact_action_reused", "action_id": ACTION_ID, "managed": False}

    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    data["actions"][ACTION_ID] = {
        "environment": "dev",
        "scope": SCOPE,
        "expires_at": expires.isoformat(),
        "command": COMMAND,
        "managed_by": MANAGED_BY,
    }
    _atomic_write(path, data)
    return {
        "status": "enabled",
        "action_id": ACTION_ID,
        "expires_at": expires.isoformat(),
        "managed": True,
    }


def disable(path: Path) -> dict:
    data = _load(path)
    existing = data["actions"].get(ACTION_ID)
    removed = False
    if isinstance(existing, dict) and existing.get("managed_by") == MANAGED_BY:
        del data["actions"][ACTION_ID]
        _atomic_write(path, data)
        removed = True
    return {"status": "disabled", "action_id": ACTION_ID, "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Autoriza uma protecao Risk3 unica do reqsys-data-platform/main")
    parser.add_argument("--config", type=Path, default=default_config_path())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    path = args.config.expanduser().resolve()
    try:
        if args.enable:
            if args.confirm != ENABLE_CONFIRM:
                raise ConfigError("enable_confirmation_invalid")
            result = enable(path, args.ttl_minutes)
        else:
            if args.confirm != DISABLE_CONFIRM:
                raise ConfigError("disable_confirmation_invalid")
            result = disable(path)
    except ConfigError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True))
        return 20
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
