#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
CONFIRM = "RECEIVE-DESKTOP-PATHS"
MAX_BODY_BYTES = 32768
DEFAULT_PORT = 8766
ALLOWED_MARKERS = (
    "desktopcontrolplanewatchdog",
    "desktopadminbroker",
)
ALLOWED_LEAFS = {
    "metadata.json",
    "install-evidence.json",
    "activate-desktop-admin-broker.cmd",
}


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def sanitize_path(raw: str) -> str | None:
    value = str(raw or "").strip().replace("/", "\\")
    if not value or len(value) > 600:
        return None
    folded = value.casefold()
    compact = "".join(ch for ch in folded if ch.isalnum())
    if not any(marker in compact for marker in ALLOWED_MARKERS):
        return None
    leaf = value.rsplit("\\", 1)[-1].casefold()
    if leaf in {"id_rsa", "id_ed25519", ".env"}:
        return None

    prefix = "c:\\users\\"
    lower = value.casefold()
    if lower.startswith(prefix):
        parts = value.split("\\")
        if len(parts) >= 5 and parts[3].casefold() == "appdata" and parts[4].casefold() == "local":
            value = "%LOCALAPPDATA%\\" + "\\".join(parts[5:])
    return value


def build_server(*, port: int, correlation_id: str, evidence_file: Path):
    done = threading.Event()
    result: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        server_version = "ReqSysNoteriPathReceiver/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if self.path != f"/collect/{correlation_id}":
                self._send(404, {"ok": False, "error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"ok": False, "error": "invalid_content_length"})
                return
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send(413, {"ok": False, "error": "body_size_invalid"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                self._send(400, {"ok": False, "error": "invalid_json"})
                return
            if not isinstance(payload, dict) or not isinstance(payload.get("paths"), list):
                self._send(400, {"ok": False, "error": "paths_required"})
                return

            paths: list[str] = []
            for item in payload["paths"][:100]:
                clean = sanitize_path(str(item))
                if clean and clean not in paths:
                    paths.append(clean)

            if not paths:
                self._send(422, {"ok": False, "error": "no_allowed_paths"})
                return

            client_hash = hashlib.sha256(str(self.client_address[0]).encode("utf-8")).hexdigest()[:16]
            evidence = {
                "schema_version": "1.0.0",
                "ok": True,
                "correlation_id": correlation_id,
                "receiver_host": socket.gethostname(),
                "received_at": now_iso(),
                "path_count": len(paths),
                "paths": paths,
                "client_ip_sha256_prefix": client_hash,
                "file_contents_read": False,
                "credentials_supplied": False,
                "secrets_read": False,
                "production_touched": False,
            }
            evidence_file.parent.mkdir(parents=True, exist_ok=True)
            evidence_file.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result.update(evidence)
            self._send(200, {"ok": True, "path_count": len(paths), "correlation_id": correlation_id})
            done.set()

    return ThreadingHTTPServer(("0.0.0.0", port), Handler), done, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        raise SystemExit("confirmation_invalid")
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise SystemExit("receiver_must_run_on_noteri")
    if not (1024 <= args.port <= 65535):
        raise SystemExit("port_invalid")
    timeout_seconds = max(30, min(args.timeout_seconds, 300))

    server, done, result = build_server(
        port=args.port,
        correlation_id=args.correlation_id,
        evidence_file=args.evidence_file,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not done.wait(timeout_seconds):
            timeout_evidence = {
                "schema_version": "1.0.0",
                "ok": False,
                "correlation_id": args.correlation_id,
                "receiver_host": socket.gethostname(),
                "received_at": now_iso(),
                "error": "receive_timeout",
                "file_contents_read": False,
                "credentials_supplied": False,
                "secrets_read": False,
                "production_touched": False,
            }
            args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_file.write_text(
                json.dumps(timeout_evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(timeout_evidence, sort_keys=True))
            return 3
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
