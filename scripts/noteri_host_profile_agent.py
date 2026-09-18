#!/usr/bin/env python3
"""Agente local mínimo para alternar o perfil NORMAL/ESTUDO do host Noteri.

O serviço escuta apenas em loopback e não expõe execução genérica de comandos.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

VALID_PROFILES = {"NORMAL", "ESTUDO"}
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8084",
    "http://localhost:8084",
}


def default_profile_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"
    return Path.home() / ".config" / "todo-global-24x7" / "host-profile.json"


def default_audit_path() -> Path:
    return default_profile_path().with_name("host-profile-audit.jsonl")


def normalize_profile(value: object) -> str:
    profile = str(value or "").strip().upper()
    if profile not in VALID_PROFILES:
        raise ValueError("profile deve ser NORMAL ou ESTUDO")
    return profile


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1",
            "host": socket.gethostname(),
            "profile": "NORMAL",
            "accepts_new_development": True,
            "source": "default",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile file deve conter objeto JSON")
    profile = normalize_profile(payload.get("profile"))
    result = dict(payload)
    result["profile"] = profile
    result["accepts_new_development"] = profile == "NORMAL"
    result["source"] = "file"
    return result


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def set_profile(path: Path, *, expected_host: str, profile: str, correlation_id: str) -> dict[str, Any]:
    host = socket.gethostname()
    if host.casefold() != expected_host.strip().casefold():
        raise ValueError(f"host atual não corresponde ao alvo esperado: {host}")
    correlation_id = correlation_id.strip()
    if not 8 <= len(correlation_id) <= 128:
        raise ValueError("correlation_id deve ter 8..128 caracteres")
    requested = normalize_profile(profile)
    before = load_profile(path)
    if before["profile"] == requested:
        return {
            **before,
            "changed": False,
            "request_correlation_id": correlation_id,
        }
    payload = {
        "schema_version": "1",
        "host": host,
        "profile": requested,
        "accepts_new_development": requested == "NORMAL",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
    }
    _atomic_write(path, payload)
    after = load_profile(path)
    if after["profile"] != requested or after["accepts_new_development"] != (requested == "NORMAL"):
        raise RuntimeError("leitura independente divergente após alteração do perfil")
    return {
        **after,
        "changed": True,
        "request_correlation_id": correlation_id,
    }


def append_audit(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass(frozen=True)
class AgentConfig:
    profile_path: Path
    audit_path: Path
    expected_host: str
    allowed_origins: frozenset[str]


class LocalAgentServer(ThreadingHTTPServer):
    config: AgentConfig


class Handler(BaseHTTPRequestHandler):
    server: LocalAgentServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _origin(self) -> str:
        return self.headers.get("Origin", "").strip()

    def _origin_allowed(self) -> bool:
        origin = self._origin()
        return not origin or origin in self.server.config.allowed_origins

    def _headers(self, status: int, *, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        origin = self._origin()
        if origin and origin in self.server.config.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)
        self.send_header("X-ReqSys-Local-Agent", "noteri-host-profile-v1")
        self.end_headers()

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    def _guard_origin(self) -> bool:
        if self._origin_allowed():
            return True
        self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin_not_allowed"})
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._guard_origin():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Correlation-Id")
        self.send_header("Access-Control-Max-Age", "300")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._guard_origin():
            return
        if self.path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "noteri-host-profile-agent",
                    "host": socket.gethostname(),
                    "loopback_only": True,
                },
            )
            return
        if self.path != "/v1/profile":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        try:
            profile = load_profile(self.server.config.profile_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        self._json(HTTPStatus.OK, {"ok": True, **profile})

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard_origin():
            return
        if self.path != "/v1/profile":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > 4096:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"})
            return
        try:
            body = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("payload deve ser objeto JSON")
            target_host = str(body.get("host") or "").strip()
            if target_host.casefold() != self.server.config.expected_host.casefold():
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": "host_target_mismatch"})
                return
            before = load_profile(self.server.config.profile_path)
            result = set_profile(
                self.server.config.profile_path,
                expected_host=self.server.config.expected_host,
                profile=str(body.get("profile") or ""),
                correlation_id=str(body.get("correlation_id") or ""),
            )
            append_audit(
                self.server.config.audit_path,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "host": socket.gethostname(),
                    "origin": self._origin() or None,
                    "before_profile": before["profile"],
                    "after_profile": result["profile"],
                    "changed": result["changed"],
                    "correlation_id": result["request_correlation_id"],
                },
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"ok": False, "error": str(exc)})
            return
        except RuntimeError as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        self._json(HTTPStatus.OK, {"ok": True, **result})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente local NORMAL/ESTUDO do Noteri")
    parser.add_argument("--bind", default=DEFAULT_BIND)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="Noteri")
    parser.add_argument("--profile-path", type=Path, default=default_profile_path())
    parser.add_argument("--audit-path", type=Path, default=default_audit_path())
    parser.add_argument("--allow-origin", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.bind not in {"127.0.0.1", "::1", "localhost"}:
        print(json.dumps({"ok": False, "error": "bind deve permanecer em loopback"}, ensure_ascii=False))
        return 2
    origins = set(DEFAULT_ORIGINS)
    origins.update(str(item).strip() for item in args.allow_origin if str(item).strip())
    config = AgentConfig(
        profile_path=args.profile_path,
        audit_path=args.audit_path,
        expected_host=args.host,
        allowed_origins=frozenset(origins),
    )
    server = LocalAgentServer((args.bind, args.port), Handler)
    server.config = config
    print(
        json.dumps(
            {
                "ok": True,
                "service": "noteri-host-profile-agent",
                "bind": args.bind,
                "port": server.server_port,
                "host": args.host,
                "profile_path": str(args.profile_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
