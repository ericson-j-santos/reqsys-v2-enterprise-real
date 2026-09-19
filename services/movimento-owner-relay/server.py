#!/usr/bin/env python3
"""Reverse relay owner-managed para comunicação Desktop -> Noteri.

O Desktop hospeda este relay. O agente Noteri inicia conexão de saída,
executa somente operações allowlistadas no Owner Data Gateway e devolve
o resultado ao Desktop. Nenhum owner token é armazenado no Desktop.
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

MAX_BODY = 1_048_576
ALLOWED_OPERATIONS = {"status", "sync", "ingest"}


class RelayState:
    def __init__(self) -> None:
        self.jobs: queue.Queue[dict[str, Any]] = queue.Queue()
        self.results: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], token: str):
        super().__init__(address, Handler)
        self.token = token
        self.state = RelayState()


class Handler(BaseHTTPRequestHandler):
    server: RelayServer

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {self.server.token}"

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("content_length_invalid") from exc
        if length <= 0 or length > MAX_BODY:
            raise ValueError("request_body_size_invalid")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("json_object_required")
        return payload

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(
                200,
                {
                    "status": "ok",
                    "service": "reqsys-owner-reverse-relay",
                    "operations": sorted(ALLOWED_OPERATIONS),
                },
            )
            return
        if not self._authorized():
            self._send(401, {"status": "unauthorized"})
            return

        parsed = urlparse(self.path)
        if parsed.path == "/result":
            request_id = (parse_qs(parsed.query).get("id") or [""])[0]
            with self.server.state.lock:
                if request_id not in self.server.state.results:
                    self._send(200, {"status": "pending", "id": request_id})
                    return
                result = self.server.state.results.pop(request_id)
            self._send(200, {"status": "done", "id": request_id, "result": result})
            return

        self._send(404, {"status": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(401, {"status": "unauthorized"})
            return
        try:
            body = self._read_json()
        except Exception as exc:
            self._send(400, {"status": "blocked", "error": type(exc).__name__})
            return

        if self.path == "/submit":
            operation = str(body.get("operation") or "")
            if operation not in ALLOWED_OPERATIONS:
                self._send(400, {"status": "blocked", "error": "operation_not_allowed"})
                return
            if operation == "sync" and not str(body.get("data_referencia") or ""):
                self._send(400, {"status": "blocked", "error": "data_referencia_required"})
                return
            if operation == "ingest" and not isinstance(body.get("payload"), dict):
                self._send(400, {"status": "blocked", "error": "payload_required"})
                return

            request_id = str(uuid.uuid4())
            self.server.state.jobs.put(
                {
                    "id": request_id,
                    "operation": operation,
                    "data_referencia": body.get("data_referencia"),
                    "payload": body.get("payload"),
                }
            )
            self._send(202, {"status": "queued", "id": request_id})
            return

        if self.path == "/agent/poll":
            timeout = min(max(float(body.get("timeout_seconds") or 10), 1), 20)
            try:
                job = self.server.state.jobs.get(timeout=timeout)
            except queue.Empty:
                self._send(200, {"status": "no_work"})
                return
            self._send(200, {"status": "work", "job": job})
            return

        if self.path == "/agent/result":
            request_id = str(body.get("id") or "")
            result = body.get("result")
            if not request_id or not isinstance(result, dict):
                self._send(400, {"status": "blocked", "error": "invalid_result"})
                return
            with self.server.state.lock:
                self.server.state.results[request_id] = result
            self._send(200, {"status": "accepted", "id": request_id})
            return

        self._send(404, {"status": "not_found"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18444)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()

    token = args.token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("token_invalid")
    RelayServer((args.bind, args.port), token).serve_forever(poll_interval=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
