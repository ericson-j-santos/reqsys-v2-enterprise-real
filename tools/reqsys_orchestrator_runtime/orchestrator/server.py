from __future__ import annotations

import json
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .core import OrchestratorStore
from .workers import DispatchAssignment, WorkerRegistry

MAX_BODY_BYTES = 1024 * 1024


def build_server(host: str, port: int, db_path: str | Path) -> ThreadingHTTPServer:
    store = OrchestratorStore(db_path)
    registry = WorkerRegistry(db_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ReqSysOrchestrator/0.2"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}
            if content_length > MAX_BODY_BYTES:
                raise ValueError("request body too large")
            raw = self.rfile.read(content_length)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        @staticmethod
        def _item_payload(item):
            return asdict(item) if item is not None else None

        @staticmethod
        def _dispatch_payload(assignment: DispatchAssignment | None):
            if assignment is None:
                return None
            return {
                "dispatch_id": assignment.dispatch_id,
                "item": asdict(assignment.item),
                "worker": registry.worker_payload(assignment.worker),
            }

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/health":
                    self._send(HTTPStatus.OK, {"ok": True})
                    return
                if path == "/v1/status":
                    payload = store.snapshot()
                    payload["workers"] = registry.snapshot()
                    self._send(HTTPStatus.OK, payload)
                    return
                if path == "/v1/workers":
                    self._send(HTTPStatus.OK, registry.snapshot())
                    return
                prefix = "/v1/work-items/"
                if path.startswith(prefix):
                    item_id = path[len(prefix):]
                    if "/" in item_id or not item_id:
                        raise KeyError(item_id)
                    item = store.get(item_id)
                    if item is None:
                        raise KeyError(item_id)
                    self._send(HTTPStatus.OK, {"item": self._item_payload(item)})
                    return
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except KeyError:
                self._send(HTTPStatus.NOT_FOUND, {"error": "work_item_not_found"})
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self._read_json()

                if path == "/v1/workers/heartbeat":
                    worker = registry.heartbeat(
                        worker_id=body.get("worker_id", ""),
                        device_name=body.get("device_name", ""),
                        roles=body.get("roles", []),
                        capabilities=body.get("capabilities", {}),
                        profile=body.get("profile", "NORMAL"),
                        controller_online=body.get("controller_online", False),
                        auth_valid=body.get("auth_valid", False),
                        controller_version=body.get("controller_version", ""),
                        correlation_id=body.get("correlation_id", ""),
                        heartbeat_ttl_seconds=body.get("heartbeat_ttl_seconds", 120),
                    )
                    self._send(
                        HTTPStatus.OK,
                        {"worker": registry.worker_payload(worker)},
                    )
                    return

                if path == "/v1/intake":
                    result = store.submit(
                        event_id=body.get("event_id", ""),
                        correlation_id=body.get("correlation_id", ""),
                        idempotency_key=body.get("idempotency_key", ""),
                        task_type=body.get("task_type", ""),
                        payload=body.get("payload", {}),
                        risk=body.get("risk", 1),
                        max_attempts=body.get("max_attempts", 3),
                        occurred_at=body.get("occurred_at"),
                    )
                    assignment = None
                    if not result["replayed"]:
                        assignment = registry.dispatch_item(
                            result["item"].id,
                            lease_seconds=body.get("lease_seconds", 60),
                        )
                    self._send(
                        HTTPStatus.CREATED if result["created"] else HTTPStatus.OK,
                        {
                            "item": self._item_payload(
                                assignment.item if assignment else result["item"]
                            ),
                            "created": result["created"],
                            "replayed": result["replayed"],
                            "route_reason": result["route_reason"],
                            "dispatch": self._dispatch_payload(assignment),
                        },
                    )
                    return

                if path == "/v1/work-items":
                    result = store.submit(
                        event_id=body.get("event_id", ""),
                        correlation_id=body.get("correlation_id", ""),
                        idempotency_key=body.get("idempotency_key", ""),
                        task_type=body.get("task_type", ""),
                        payload=body.get("payload", {}),
                        risk=body.get("risk", 1),
                        max_attempts=body.get("max_attempts", 3),
                        occurred_at=body.get("occurred_at"),
                    )
                    self._send(
                        HTTPStatus.CREATED if result["created"] else HTTPStatus.OK,
                        {
                            "item": self._item_payload(result["item"]),
                            "created": result["created"],
                            "replayed": result["replayed"],
                            "route_reason": result["route_reason"],
                        },
                    )
                    return

                if path == "/v1/dispatch":
                    assignment = registry.dispatch_next(
                        lease_seconds=body.get("lease_seconds", 60)
                    )
                    self._send(
                        HTTPStatus.OK,
                        {"dispatch": self._dispatch_payload(assignment)},
                    )
                    return

                if path == "/v1/leases":
                    store.recover_expired_leases()
                    item = store.lease_next(
                        worker_role=body.get("worker_role", ""),
                        worker_id=body.get("worker_id", ""),
                        lease_seconds=body.get("lease_seconds", 60),
                    )
                    self._send(
                        HTTPStatus.OK,
                        {"item": self._item_payload(item)},
                    )
                    return

                if path == "/v1/recover":
                    self._send(HTTPStatus.OK, store.recover_expired_leases())
                    return

                prefix = "/v1/work-items/"
                if path.startswith(prefix):
                    remainder = path[len(prefix):]
                    parts = remainder.split("/")
                    if len(parts) != 2 or not parts[0]:
                        raise KeyError(remainder)
                    item_id, action = parts
                    if action == "complete":
                        item = store.complete(
                            item_id,
                            worker_id=body.get("worker_id", ""),
                            result=body.get("result", {}),
                        )
                        self._send(HTTPStatus.OK, {"item": self._item_payload(item)})
                        return
                    if action == "fail":
                        item = store.fail(
                            item_id,
                            worker_id=body.get("worker_id", ""),
                            error=body.get("error", ""),
                        )
                        self._send(HTTPStatus.OK, {"item": self._item_payload(item)})
                        return
                    raise KeyError(remainder)

                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except json.JSONDecodeError:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            except ValueError as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except KeyError:
                self._send(HTTPStatus.NOT_FOUND, {"error": "work_item_not_found"})
            except PermissionError as exc:
                self._send(HTTPStatus.CONFLICT, {"error": str(exc)})
            except RuntimeError as exc:
                self._send(HTTPStatus.CONFLICT, {"error": str(exc)})
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

    return ThreadingHTTPServer((host, port), Handler)


def serve() -> None:
    host = os.getenv("ORCH_HOST", "127.0.0.1")
    port = int(os.getenv("ORCH_PORT", "8787"))
    db_path = os.getenv("ORCH_DB_PATH", "data/orchestrator.db")
    server = build_server(host, port, db_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
