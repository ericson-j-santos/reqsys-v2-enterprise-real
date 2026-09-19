#!/usr/bin/env python3
"""Configura o provider Ollama do ReqSys no perfil do usuário Windows.

Não lê nem grava .env e não manipula credenciais. Persistência fica em
HKCU\\Environment e vale para processos iniciados após a alteração.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ENV_KEY = r"Environment"
MODEL_KEYS = ("CODEX_OLLAMA_MODEL", "CODEX_OLLAMA_GATEWAY_MODEL")
BASE_URL_KEY = "CODEX_OLLAMA_BASE_URL"
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class ConfigError(RuntimeError):
    pass


def validate_model(value: str) -> str:
    model = value.strip()
    if not MODEL_RE.fullmatch(model):
        raise ConfigError("modelo inválido")
    return model


def validate_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ConfigError("base-url deve ser HTTP loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("base-url não pode conter credenciais, query ou fragmento")
    return value.rstrip("/")


def desired_values(model: str, base_url: str) -> dict[str, str]:
    model = validate_model(model)
    base_url = validate_base_url(base_url)
    return {
        "CODEX_OLLAMA_MODEL": model,
        "CODEX_OLLAMA_GATEWAY_MODEL": model,
        "CODEX_OLLAMA_BASE_URL": base_url,
    }


def backup_path() -> Path:
    root = os.getenv("LOCALAPPDATA")
    if not root:
        raise ConfigError("LOCALAPPDATA não definido")
    return Path(root) / "ReqSys" / "Codex" / "ollama-provider-backup.json"


def _winreg():
    if sys.platform != "win32":
        raise ConfigError("operação persistente suportada somente no Windows")
    import winreg
    return winreg


def read_user_values() -> dict[str, str | None]:
    winreg = _winreg()
    result: dict[str, str | None] = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return {name: None for name in (*MODEL_KEYS, BASE_URL_KEY)}
    with key:
        for name in (*MODEL_KEYS, BASE_URL_KEY):
            try:
                value, _ = winreg.QueryValueEx(key, name)
                result[name] = str(value)
            except FileNotFoundError:
                result[name] = None
    return result


def _write_user_values(values: dict[str, str | None]) -> None:
    winreg = _winreg()
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, ENV_KEY, 0, winreg.KEY_SET_VALUE)
    with key:
        for name, value in values.items():
            if value is None:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _broadcast_environment_change() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    result = ctypes.c_ulong()
    sent = ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Environment",
        SMTO_ABORTIFHUNG,
        5000,
        ctypes.byref(result),
    )
    return bool(sent)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def apply(model: str, base_url: str) -> dict[str, Any]:
    desired = desired_values(model, base_url)
    before = read_user_values()
    path = backup_path()
    _atomic_json(
        path,
        {
            "version": 1,
            "keys": before,
        },
    )
    _write_user_values(desired)
    broadcast = _broadcast_environment_change()
    after = read_user_values()
    if after != desired:
        raise ConfigError("validação pós-gravação divergiu")
    return {
        "result": "APPLIED",
        "before": before,
        "after": after,
        "backup_path": str(path),
        "environment_broadcast": broadcast,
        "restart_required_for_existing_processes": True,
    }


def rollback() -> dict[str, Any]:
    path = backup_path()
    if not path.is_file():
        raise ConfigError("backup de rollback inexistente")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("backup de rollback inválido") from exc
    keys = payload.get("keys")
    if not isinstance(keys, dict):
        raise ConfigError("backup de rollback sem chaves")
    allowed = {*MODEL_KEYS, BASE_URL_KEY}
    if set(keys) != allowed:
        raise ConfigError("backup contém conjunto de chaves inesperado")
    before = read_user_values()
    restore = {name: keys.get(name) for name in allowed}
    _write_user_values(restore)
    broadcast = _broadcast_environment_change()
    after = read_user_values()
    if after != restore:
        raise ConfigError("validação pós-rollback divergiu")
    return {
        "result": "ROLLED_BACK",
        "before": before,
        "after": after,
        "environment_broadcast": broadcast,
        "restart_required_for_existing_processes": True,
    }


def status() -> dict[str, Any]:
    return {
        "result": "STATUS",
        "values": read_user_values(),
        "backup_exists": backup_path().is_file(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configuração local do provider Ollama")
    sub = parser.add_subparsers(dest="action", required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--model", required=True)
    apply_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub.add_parser("status")
    sub.add_parser("rollback")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "apply":
            result = apply(args.model, args.base_url)
        elif args.action == "rollback":
            result = rollback()
        else:
            result = status()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigError as exc:
        print(json.dumps({"result": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
