#!/usr/bin/env python3
"""E2E físico e efêmero do Codex Worker Pool entre dois hosts.

O servidor usa WorkerPoolStore real com SQLite temporário. O cliente remoto
executa somente ações fixas do cenário; não há shell remoto, segredo ou efeito
fora do banco temporário.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "codex-worker-pool"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.store import WorkerPoolStore  # noqa: E402


MAX_MESSAGE = 4096


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def send_request(host: str, port: int, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_MESSAGE:
        raise ValueError("mensagem excede limite")
    last_error: OSError | None = None
    for _ in range(20):
        try:
            with socket.create_connection((host, port), timeout=timeout) as client:
                client.settimeout(timeout)
                client.sendall(encoded)
                raw = client.recv(MAX_MESSAGE)
            return json.loads(raw.decode("utf-8"))
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise last_error or ConnectionError("conexão não estabelecida")


class Scenario:
    def __init__(self, db_path: Path, rules_sha: str, reqsys_sha: str, correlation_id: str, lease_seconds: int) -> None:
        self.rules_sha = rules_sha.lower()
        self.reqsys_sha = reqsys_sha.lower()
        self.correlation_id = correlation_id
        self.lease_seconds = lease_seconds
        self.store = WorkerPoolStore(
            db_path,
            heartbeat_ttl_seconds=120,
            default_lease_seconds=30,
            default_max_attempts=3,
            expected_rules_sha=self.rules_sha,
        )
        self.positive_task_id = ""
        self.lease_task_id = ""
        self.desktop_lease_token = ""
        self.observed: dict[str, Any] = {}
        self.done = False
        self._prepare()

    def _register(self, worker_id: str, host: str, role: str) -> None:
        self.store.register_worker(
            worker_id=worker_id,
            host=host,
            role=role,
            profile="NORMAL",
            capacity_score=70 if host == "DESKTOP-PDQK954" else 50,
            controller_version="0.2.51",
            rules_sha=self.rules_sha,
            gateway_ok=True,
            state_validated=True,
            worktree_root=f"C:/dev/chatgpt-workers/{worker_id}",
            correlation_id=f"{self.correlation_id}-{worker_id}",
        )

    def _prepare(self) -> None:
        self._register("desktop-builder", "DESKTOP-PDQK954", "builder")
        self._register("noteri-validator", "Noteri", "validator")
        self._register("noteri-builder-control", "Noteri", "builder")

        # Este cenário mantém duas tasks simultaneamente ativas no mesmo repositório:
        # uma aguardando validação e outra exercitando expiração/recuperação de lease.
        # A lane padrão continua max_in_flight=1; somente o fixture E2E exige capacidade 2.
        self.store.configure_repository(
            repository="ericson-j-santos/reqsys-v2-enterprise-real",
            max_in_flight=2,
        )

        positive, created = self.store.enqueue_task(
            repository="ericson-j-santos/reqsys-v2-enterprise-real",
            issue_number=1769,
            request_id=f"{self.correlation_id}-positive",
            correlation_id=f"{self.correlation_id}-enqueue-positive",
            priority=1,
            base_sha=self.reqsys_sha,
            max_attempts=3,
        )
        if not created:
            raise RuntimeError("positive task não foi criada")
        self.positive_task_id = positive["task_id"]
        claimed, lease = self.store.claim_task(
            worker_id="desktop-builder",
            role="builder",
            correlation_id=f"{self.correlation_id}-positive-claim",
            lease_seconds=30,
        )
        if not claimed or not lease or claimed["task_id"] != self.positive_task_id:
            raise RuntimeError("Builder não adquiriu positive task")
        self.store.start_task(
            task_id=self.positive_task_id,
            worker_id="desktop-builder",
            lease_token=lease.lease_token,
            correlation_id=f"{self.correlation_id}-positive-start",
        )
        self.store.submit_for_validation(
            task_id=self.positive_task_id,
            worker_id="desktop-builder",
            lease_token=lease.lease_token,
            produced_sha=self.reqsys_sha,
            correlation_id=f"{self.correlation_id}-positive-handoff",
        )

        lease_task, created = self.store.enqueue_task(
            repository="ericson-j-santos/reqsys-v2-enterprise-real",
            issue_number=1769,
            request_id=f"{self.correlation_id}-lease",
            correlation_id=f"{self.correlation_id}-enqueue-lease",
            priority=2,
            base_sha=self.reqsys_sha,
            max_attempts=3,
        )
        if not created:
            raise RuntimeError("lease task não foi criada")
        self.lease_task_id = lease_task["task_id"]
        claimed, lease = self.store.claim_task(
            worker_id="desktop-builder",
            role="builder",
            correlation_id=f"{self.correlation_id}-lease-claim",
            lease_seconds=30,
        )
        if not claimed or not lease or claimed["task_id"] != self.lease_task_id:
            raise RuntimeError("Builder não adquiriu lease task")
        self.desktop_lease_token = lease.lease_token
        self.store.start_task(
            task_id=self.lease_task_id,
            worker_id="desktop-builder",
            lease_token=lease.lease_token,
            correlation_id=f"{self.correlation_id}-lease-start",
        )

    def handle(self, request: dict[str, Any], peer_ipv4: str) -> dict[str, Any]:
        if request.get("correlation_id") != self.correlation_id:
            return {"ok": False, "error": "correlation_id_mismatch"}

        action = request.get("action")
        if action == "validate_positive":
            task, lease = self.store.claim_task(
                worker_id="noteri-validator",
                role="validator",
                correlation_id=f"{self.correlation_id}-validator-claim",
            )
            if not task or not lease or task["task_id"] != self.positive_task_id:
                return {"ok": False, "error": "validator_claim_failed"}
            completed = self.store.complete_task(
                task_id=self.positive_task_id,
                worker_id="noteri-validator",
                lease_token=lease.lease_token,
                correlation_id=f"{self.correlation_id}-validator-complete",
            )
            self.observed["validated"] = completed["state"] == "completed"
            return {
                "ok": self.observed["validated"],
                "action": action,
                "peer_ipv4": peer_ipv4,
                "task_id": completed["task_id"],
                "state": completed["state"],
                "produced_sha": completed["produced_sha"],
                "builder_worker_id": completed["builder_worker_id"],
                "validator_worker_id": completed["validator_worker_id"],
            }

        if action == "replay_positive":
            replay, created = self.store.enqueue_task(
                repository="ericson-j-santos/reqsys-v2-enterprise-real",
                issue_number=1769,
                request_id=f"{self.correlation_id}-positive",
                correlation_id=f"{self.correlation_id}-replay",
                priority=1,
                base_sha=self.reqsys_sha,
                max_attempts=3,
            )
            same = replay["task_id"] == self.positive_task_id
            self.observed["replay"] = (not created) and same
            return {"ok": self.observed["replay"], "action": action, "created": created, "same_task": same}

        if action == "duplicate_claim":
            self.store.renew_lease(
                task_id=self.lease_task_id,
                worker_id="desktop-builder",
                lease_token=self.desktop_lease_token,
                correlation_id=f"{self.correlation_id}-lease-renew",
                lease_seconds=self.lease_seconds,
            )
            claimed, _lease = self.store.claim_task(
                worker_id="noteri-builder-control",
                role="builder",
                correlation_id=f"{self.correlation_id}-duplicate-claim",
            )
            blocked = claimed is None
            self.observed["duplicate_blocked"] = blocked
            return {
                "ok": blocked,
                "action": action,
                "claimed": claimed is not None,
                "lease_seconds": self.lease_seconds,
            }

        if action == "recover_expired":
            recovered = self.store.recover_expired_leases()
            claimed, lease = self.store.claim_task(
                worker_id="noteri-builder-control",
                role="builder",
                correlation_id=f"{self.correlation_id}-recovered-claim",
            )
            same = bool(claimed and claimed["task_id"] == self.lease_task_id)
            attempt_count = int(claimed["attempt_count"]) if claimed else 0
            self.observed["recovered"] = recovered >= 1 and same and lease is not None and attempt_count == 2
            return {
                "ok": self.observed["recovered"],
                "action": action,
                "recovered_count": recovered,
                "same_task": same,
                "attempt_count": attempt_count,
                "leased_by": claimed["leased_by"] if claimed else None,
            }

        if action == "readback":
            positive = self.store.get_task(self.positive_task_id)
            lease_task = self.store.get_task(self.lease_task_id)
            ok = (
                positive["state"] == "completed"
                and positive["produced_sha"] == self.reqsys_sha
                and positive["builder_worker_id"] == "desktop-builder"
                and positive["validator_worker_id"] == "noteri-validator"
                and lease_task["leased_by"] == "noteri-builder-control"
                and int(lease_task["attempt_count"]) == 2
            )
            self.observed["readback"] = ok
            return {
                "ok": ok,
                "action": action,
                "positive_state": positive["state"],
                "positive_sha": positive["produced_sha"],
                "lease_state": lease_task["state"],
                "lease_attempt_count": lease_task["attempt_count"],
                "lease_leased_by": lease_task["leased_by"],
            }

        if action == "finish":
            required = ("validated", "replay", "duplicate_blocked", "recovered", "readback")
            passed = all(self.observed.get(name) is True for name in required)
            self.done = True
            return {
                "ok": passed,
                "action": action,
                "overall_passed": passed,
                "checks": {name: self.observed.get(name) is True for name in required},
                "reqsys_sha": self.reqsys_sha,
                "rules_sha": self.rules_sha,
            }

        return {"ok": False, "error": "unsupported_action"}


def run_server(bind_host: str, port: int, scenario: Scenario, timeout: float) -> dict[str, Any]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(timeout)
        server.bind((bind_host, port))
        server.listen(4)
        emit({"ok": True, "mode": "server", "state": "listening", "bind_host": bind_host, "port": port})
        handled = 0
        while not scenario.done and handled < 10:
            try:
                conn, peer = server.accept()
            except TimeoutError:
                return {
                    "ok": False,
                    "mode": "server",
                    "state": "timeout",
                    "handled": handled,
                }
            with conn:
                conn.settimeout(timeout)
                raw = conn.recv(MAX_MESSAGE)
                try:
                    request = json.loads(raw.decode("utf-8"))
                    response = scenario.handle(request, str(peer[0]))
                except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
                    response = {"ok": False, "error": type(exc).__name__}
                conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))
                handled += 1
        return {"ok": scenario.done, "mode": "server", "state": "completed", "handled": handled}


def run_client(host: str, port: int, correlation_id: str, lease_wait: float, timeout: float) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    for action in ("validate_positive", "replay_positive", "duplicate_claim"):
        result = send_request(
            host,
            port,
            {"action": action, "correlation_id": correlation_id},
            timeout,
        )
        results[action] = result
        emit(result)
        if not result.get("ok"):
            return {"ok": False, "failed_action": action, "results": results}

    time.sleep(lease_wait)

    for action in ("recover_expired", "readback", "finish"):
        result = send_request(
            host,
            port,
            {"action": action, "correlation_id": correlation_id},
            timeout,
        )
        results[action] = result
        emit(result)
        if not result.get("ok"):
            return {"ok": False, "failed_action": action, "results": results}

    return {
        "ok": results["finish"].get("overall_passed") is True,
        "mode": "client",
        "correlation_id": correlation_id,
        "results": results,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="E2E físico do Codex Worker Pool")
    sub = root.add_subparsers(dest="mode", required=True)

    server = sub.add_parser("server")
    server.add_argument("--bind-host", required=True)
    server.add_argument("--port", type=int, default=18098)
    server.add_argument("--rules-sha", required=True)
    server.add_argument("--reqsys-sha", required=True)
    server.add_argument("--correlation-id", required=True)
    server.add_argument("--lease-seconds", type=int, default=3)
    server.add_argument("--timeout", type=float, default=60.0)

    client = sub.add_parser("client")
    client.add_argument("--host", required=True)
    client.add_argument("--port", type=int, default=18098)
    client.add_argument("--correlation-id", required=True)
    client.add_argument("--lease-wait", type=float, default=3.5)
    client.add_argument("--timeout", type=float, default=10.0)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.mode == "server":
            with tempfile.TemporaryDirectory(prefix="reqsys-cwp-e2e-") as temp:
                scenario = Scenario(
                    Path(temp) / "worker-pool.db",
                    args.rules_sha,
                    args.reqsys_sha,
                    args.correlation_id,
                    args.lease_seconds,
                )
                result = run_server(args.bind_host, args.port, scenario, args.timeout)
                emit(result)
                return 0 if result["ok"] else 4

        result = run_client(args.host, args.port, args.correlation_id, args.lease_wait, args.timeout)
        emit(result)
        return 0 if result["ok"] else 4
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        emit({"ok": False, "mode": args.mode, "error": type(exc).__name__})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
