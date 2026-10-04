#!/usr/bin/env python3
"""Gateway privado da fonte owner-managed da Prospecção Movimento."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import ipaddress
import json
import socket
import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

OVERLAY = ipaddress.ip_network("100.64.0.0/10")
MAX_BODY = 1024 * 1024


def _candidate_ipv4() -> list[str]:
    values: list[str] = []
    try:
        import psutil  # type: ignore
        for addresses in psutil.net_if_addrs().values():
            for item in addresses:
                if item.family == socket.AF_INET:
                    values.append(str(item.address))
    except Exception:
        pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            values.append(str(item[4][0]))
    except OSError:
        pass
    return sorted(set(values))


def detect_overlay_ipv4() -> str:
    for value in _candidate_ipv4():
        try:
            addr = ipaddress.ip_address(value)
        except ValueError:
            continue
        if addr in OVERLAY:
            return value
    raise RuntimeError("private_overlay_ipv4_not_found")


def _load_owner_module(path: Path):
    spec = importlib.util.spec_from_file_location("movimento_email_owner_source_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("owner_source_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OwnerGateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, config: dict[str, Any]):
        bind_ip = str(config["bind_ip"])
        port = int(config["port"])
        addr = ipaddress.ip_address(bind_ip)
        if addr not in OVERLAY and not addr.is_loopback:
            raise RuntimeError("gateway_bind_must_be_private_overlay_or_loopback")
        super().__init__((bind_ip, port), Handler)
        self.config = config
        self.token = Path(config["token_file"]).read_text(encoding="utf-8").strip()
        if len(self.token) < 32:
            raise RuntimeError("gateway_token_invalid")
        self.owner = _load_owner_module(Path(config["owner_module"]))


class Handler(BaseHTTPRequestHandler):
    server: OwnerGateway

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):].strip(), self.server.token)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send(401, {"status": "unauthorized"})
        return False

    def _read_json(self) -> dict[str, Any]:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_len)
        except ValueError as exc:
            raise ValueError("content_length_invalid") from exc
        if length <= 0 or length > MAX_BODY:
            raise ValueError("request_body_size_invalid")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request_json_object_required")
        return payload

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {
                "status": "ok",
                "logical_name": self.server.config["logical_name"],
                "node_name": socket.gethostname(),
                "source_authority": "owner_managed",
                "synthetic": False,
                "production_touched": False,
            })
            return
        if self.path == "/status":
            if not self._require_auth():
                return
            result = self.server.owner.validate(
                "localhost",
                self.server.config["source_db"],
                self.server.config["target_db"],
            )
            self._send(200 if result["status"] == "passed" else 503, result)
            return
        self._send(404, {"status": "not_found"})

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        try:
            payload = self._read_json()
            if self.path == "/ingest":
                runtime = Path(self.server.config["runtime_dir"])
                runtime.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".json", prefix="ingest-", dir=runtime, delete=False
                ) as tmp:
                    json.dump(payload, tmp, ensure_ascii=False)
                    temp_path = Path(tmp.name)
                try:
                    result = self.server.owner.ingest(
                        "localhost",
                        self.server.config["source_db"],
                        temp_path,
                        str(payload.get("correlation_id") or "gateway-ingest"),
                    )
                finally:
                    temp_path.unlink(missing_ok=True)
                self._send(200, result)
                return
            if self.path == "/sync":
                ref = date.fromisoformat(str(payload.get("data_referencia") or ""))
                result = self.server.owner.sync(
                    "localhost",
                    self.server.config["source_db"],
                    self.server.config["target_db"],
                    ref,
                )
                self._send(200, result)
                return
            self._send(404, {"status": "not_found"})
        except Exception as exc:
            self._send(400, {"status": "blocked", "error": type(exc).__name__})


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "logical_name", "bind_ip", "port", "token_file", "owner_module",
        "runtime_dir", "source_db", "target_db",
    }
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise RuntimeError("gateway_config_invalid")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    server = OwnerGateway(load_config(args.config))
    server.serve_forever(poll_interval=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
