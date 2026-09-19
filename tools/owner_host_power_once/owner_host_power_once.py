#!/usr/bin/env python3
"""One-time owner-authorized host reboot route.

This is intentionally separate from owner_risk3_gateway.py so the general
Risk 3 gateway continues to deny reboot/shutdown/poweroff.

The route supports exactly one operation: reboot the current local Windows
host after a short-lived, owner-bound authorization has been materialized.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EXIT_POLICY = 20
EXIT_COMMAND = 22
EXIT_EXPIRED = 26

MAX_WINDOW_MINUTES = 15
AUTHORIZE_CONFIRM = "AUTHORIZE-ONE-TIME-REBOOT"
EXECUTE_CONFIRM = "EXECUTE-ONE-TIME-REBOOT"
REVOKE_CONFIRM = "REVOKE-ONE-TIME-REBOOT"
ACTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


class HostPowerError(RuntimeError):
    def __init__(self, message: str, exit_code: int = EXIT_POLICY) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def owner_fingerprint() -> str:
    identity = f"{getpass.getuser()}@{socket.gethostname()}".encode(
        "utf-8", errors="replace"
    )
    return hashlib.sha256(identity).hexdigest()


def default_state_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "ReqSys" / "CommandGateway"
    return Path.home() / ".reqsys-command-gateway"


def default_config_path() -> Path:
    return default_state_dir() / "owner-host-power-once.local.json"


def audit_path() -> Path:
    return default_state_dir() / "owner-host-power-audit.jsonl"


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise HostPowerError("timestamp inválido") from exc
    if parsed.tzinfo is None:
        raise HostPowerError("timestamp deve conter timezone")
    return parsed.astimezone(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def append_audit(payload: dict[str, Any]) -> None:
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def validate_action_id(action_id: str) -> str:
    if not ACTION_ID_RE.fullmatch(action_id):
        raise HostPowerError("action_id inválido")
    return action_id


def authorize(
    *,
    action_id: str,
    host: str,
    minutes: int,
    confirm: str,
    config_path: Path,
    authorization_ref: str,
) -> dict[str, Any]:
    validate_action_id(action_id)
    if confirm != AUTHORIZE_CONFIRM:
        raise HostPowerError("confirmação de autorização inválida")
    local_host = socket.gethostname()
    if host.casefold() != local_host.casefold():
        raise HostPowerError("host solicitado não corresponde ao host local")
    if minutes < 1 or minutes > MAX_WINDOW_MINUTES:
        raise HostPowerError(
            f"janela deve estar entre 1 e {MAX_WINDOW_MINUTES} minutos"
        )
    if not authorization_ref.strip():
        raise HostPowerError("authorization_ref é obrigatório")

    now = utc_now()
    payload = {
        "version": 1,
        "enabled": True,
        "action_id": action_id,
        "operation": "reboot",
        "host": local_host,
        "scope": f"host://{local_host}/reboot-once",
        "owner_fingerprint": owner_fingerprint(),
        "authorized_at": utc_iso(now),
        "expires_at": utc_iso(now + timedelta(minutes=minutes)),
        "authorization_ref_sha256": hashlib.sha256(
            authorization_ref.encode("utf-8")
        ).hexdigest(),
        "consumed_at": None,
    }
    atomic_json(config_path, payload)
    append_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_authorized",
            "action_id": action_id,
            "host": local_host,
            "operation": "reboot",
            "expires_at": payload["expires_at"],
            "authorization_ref_sha256": payload["authorization_ref_sha256"],
            "timestamp": utc_iso(),
        }
    )
    return {
        "ok": True,
        "action_id": action_id,
        "host": local_host,
        "operation": "reboot",
        "expires_at": payload["expires_at"],
    }


def load_authorization(
    *,
    action_id: str,
    config_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_action_id(action_id)
    if not config_path.is_file():
        raise HostPowerError("autorização de host power inexistente")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostPowerError("autorização de host power inválida") from exc

    if payload.get("version") != 1 or payload.get("enabled") is not True:
        raise HostPowerError("autorização de host power não está habilitada")
    if payload.get("action_id") != action_id:
        raise HostPowerError("action_id não corresponde à autorização")
    if payload.get("operation") != "reboot":
        raise HostPowerError("somente reboot é permitido")
    local_host = socket.gethostname()
    if str(payload.get("host", "")).casefold() != local_host.casefold():
        raise HostPowerError("autorização pertence a outro host")
    if payload.get("scope") != f"host://{local_host}/reboot-once":
        raise HostPowerError("escopo de host power inválido")
    if payload.get("owner_fingerprint") != owner_fingerprint():
        raise HostPowerError("autorização pertence a outro usuário/host")
    if payload.get("consumed_at"):
        raise HostPowerError("autorização já foi consumida")

    authorized_at = parse_utc(payload.get("authorized_at"))
    expires_at = parse_utc(payload.get("expires_at"))
    if expires_at - authorized_at > timedelta(
        minutes=MAX_WINDOW_MINUTES, seconds=5
    ):
        raise HostPowerError("janela de autorização excede o limite")
    reference = now or utc_now()
    if expires_at <= reference:
        raise HostPowerError("autorização expirada", EXIT_EXPIRED)
    return payload


def consume_authorization(
    *, config_path: Path, payload: dict[str, Any], correlation_id: str
) -> dict[str, Any]:
    consumed = dict(payload)
    consumed["consumed_at"] = utc_iso()
    consumed["correlation_id"] = correlation_id
    atomic_json(config_path, consumed)
    append_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_consumed",
            "action_id": consumed["action_id"],
            "host": consumed["host"],
            "operation": "reboot",
            "correlation_id": correlation_id,
            "timestamp": consumed["consumed_at"],
        }
    )
    return consumed


def submit_reboot(delay_seconds: int) -> subprocess.CompletedProcess[str]:
    if os.name != "nt":
        raise HostPowerError("reboot governado suportado somente no Windows")
    if delay_seconds < 5 or delay_seconds > 60:
        raise HostPowerError("delay de reboot deve estar entre 5 e 60 segundos")
    return subprocess.run(
        [
            "shutdown.exe",
            "/r",
            "/t",
            str(delay_seconds),
            "/c",
            "ReqSys governed one-time reboot validation",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=15,
        check=False,
    )


def execute(
    *,
    action_id: str,
    confirm: str,
    config_path: Path,
    correlation_id: str,
    delay_seconds: int,
) -> dict[str, Any]:
    if confirm != EXECUTE_CONFIRM:
        raise HostPowerError("confirmação de execução inválida")
    payload = load_authorization(action_id=action_id, config_path=config_path)

    # Fail closed: consume before submitting reboot so the authorization cannot
    # be replayed even if the process loses connectivity immediately afterward.
    consume_authorization(
        config_path=config_path,
        payload=payload,
        correlation_id=correlation_id,
    )
    completed = submit_reboot(delay_seconds)
    append_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_submitted",
            "action_id": action_id,
            "host": payload["host"],
            "operation": "reboot",
            "correlation_id": correlation_id,
            "returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(
                completed.stdout.encode("utf-8", errors="replace")
            ).hexdigest(),
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode("utf-8", errors="replace")
            ).hexdigest(),
            "timestamp": utc_iso(),
        }
    )
    if completed.returncode != 0:
        raise HostPowerError(
            f"reboot governado falhou com exit={completed.returncode}",
            EXIT_COMMAND,
        )
    return {
        "ok": True,
        "action_id": action_id,
        "host": payload["host"],
        "operation": "reboot",
        "correlation_id": correlation_id,
        "delay_seconds": delay_seconds,
        "consumed": True,
    }


def revoke(*, confirm: str, config_path: Path) -> dict[str, Any]:
    if confirm != REVOKE_CONFIRM:
        raise HostPowerError("confirmação de revogação inválida")
    if config_path.exists():
        config_path.unlink()
    append_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_revoked",
            "timestamp": utc_iso(),
        }
    )
    return {"ok": True, "revoked": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exceção governada e consumível para um único reboot local"
    )
    parser.add_argument("--config", type=Path, default=default_config_path())
    sub = parser.add_subparsers(dest="command", required=True)

    authorize_parser = sub.add_parser("authorize")
    authorize_parser.add_argument("--action-id", required=True)
    authorize_parser.add_argument("--host", required=True)
    authorize_parser.add_argument("--minutes", type=int, default=10)
    authorize_parser.add_argument("--authorization-ref", required=True)
    authorize_parser.add_argument("--confirm", required=True)

    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--action-id", required=True)
    execute_parser.add_argument("--correlation-id", default=None)
    execute_parser.add_argument("--delay-seconds", type=int, default=5)
    execute_parser.add_argument("--confirm", required=True)

    revoke_parser = sub.add_parser("revoke")
    revoke_parser.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "authorize":
            result = authorize(
                action_id=args.action_id,
                host=args.host,
                minutes=args.minutes,
                confirm=args.confirm,
                config_path=args.config,
                authorization_ref=args.authorization_ref,
            )
        elif args.command == "execute":
            result = execute(
                action_id=args.action_id,
                confirm=args.confirm,
                config_path=args.config,
                correlation_id=args.correlation_id or str(uuid.uuid4()),
                delay_seconds=args.delay_seconds,
            )
        else:
            result = revoke(confirm=args.confirm, config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except HostPowerError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "exit_code": exc.exit_code},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
