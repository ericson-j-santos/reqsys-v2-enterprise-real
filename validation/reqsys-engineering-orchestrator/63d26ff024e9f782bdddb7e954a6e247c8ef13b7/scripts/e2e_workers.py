from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from orchestrator.core import COMPLETED, OrchestratorStore
from orchestrator.server import build_server
from orchestrator.workers import WorkerRegistry


def call(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def heartbeat(
    base: str,
    *,
    worker_id: str,
    device_name: str,
    profile: str,
    priority: int,
    online: bool = True,
) -> dict:
    status, payload = call(
        "POST",
        base + "/v1/workers/heartbeat",
        {
            "worker_id": worker_id,
            "device_name": device_name,
            "roles": ["builder", "ci-remediator", "e2e-validator"],
            "capabilities": {
                "dispatch_priority": priority,
                "transport_broadcast_v1": True,
                "python_version": "3.12.10",
            },
            "profile": profile,
            "controller_online": online,
            "auth_valid": True,
            "controller_version": "0.2.51",
            "correlation_id": "corr-live-host-shape-e2e",
            "heartbeat_ttl_seconds": 120,
        },
    )
    assert status == 200, (status, payload)
    return payload["worker"]


def intake(base: str, event_id: str, key: str, task_type: str, risk: int = 1) -> dict:
    status, payload = call(
        "POST",
        base + "/v1/intake",
        {
            "event_id": event_id,
            "correlation_id": "corr-live-host-shape-e2e",
            "idempotency_key": key,
            "task_type": task_type,
            "payload": {"repository": "reqsys-v2-enterprise-real"},
            "risk": risk,
            "lease_seconds": 30,
        },
    )
    assert status == 201, (status, payload)
    return payload


def complete(base: str, item_id: str, worker_id: str, evidence: str) -> None:
    status, payload = call(
        "POST",
        base + f"/v1/work-items/{item_id}/complete",
        {
            "worker_id": worker_id,
            "result": {"evidence": evidence},
        },
    )
    assert status == 200, (status, payload)
    assert payload["item"]["status"] == COMPLETED


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "orchestrator.db"
        server = build_server("127.0.0.1", 0, db_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        try:
            desktop = heartbeat(
                base,
                worker_id="desktop-pdqk954",
                device_name="DESKTOP-PDQK954",
                profile="NORMAL",
                priority=10,
            )
            noteri = heartbeat(
                base,
                worker_id="noteri",
                device_name="Noteri",
                profile="NORMAL",
                priority=20,
            )
            assert desktop["eligible"] is True
            assert noteri["eligible"] is True

            first = intake(
                base,
                "evt-auto-dispatch-001",
                "reqsys:auto-dispatch:001",
                "implementation",
            )
            assert first["dispatch"] is not None
            assert first["dispatch"]["worker"]["worker_id"] == "desktop-pdqk954"
            first_id = first["item"]["id"]
            complete(base, first_id, "desktop-pdqk954", "desktop-e2e-ok")

            heartbeat(
                base,
                worker_id="desktop-pdqk954",
                device_name="DESKTOP-PDQK954",
                profile="ESTUDO",
                priority=10,
            )
            second = intake(
                base,
                "evt-auto-dispatch-002",
                "reqsys:auto-dispatch:002",
                "implementation",
            )
            assert second["dispatch"] is not None
            assert second["dispatch"]["worker"]["worker_id"] == "noteri"
            second_id = second["item"]["id"]
            complete(base, second_id, "noteri", "noteri-e2e-ok")

            risk3 = intake(
                base,
                "evt-auto-dispatch-risk3",
                "reqsys:auto-dispatch:risk3",
                "deploy production",
                risk=3,
            )
            assert risk3["item"]["target_worker"] == "human-gate"
            assert risk3["dispatch"] is None

            status, replay = call(
                "POST",
                base + "/v1/intake",
                {
                    "event_id": "evt-auto-dispatch-002",
                    "correlation_id": "corr-live-host-shape-e2e",
                    "idempotency_key": "reqsys:auto-dispatch:002",
                    "task_type": "implementation",
                    "payload": {"repository": "reqsys-v2-enterprise-real"},
                    "risk": 1,
                    "lease_seconds": 30,
                },
            )
            assert status == 200, (status, replay)
            assert replay["replayed"] is True
            assert replay["dispatch"] is None

            status, snapshot = call("GET", base + "/v1/status")
            assert status == 200, (status, snapshot)
            assert snapshot["workers"]["total"] == 2
            assert snapshot["workers"]["eligible"] == 1
            assert snapshot["workers"]["dispatch_events"] == 2
            assert snapshot["by_status"][COMPLETED] == 2

            independent_store = OrchestratorStore(db_path)
            independent_registry = WorkerRegistry(db_path)
            assert independent_store.get(first_id).status == COMPLETED
            assert independent_store.get(second_id).status == COMPLETED
            assert independent_registry.snapshot()["dispatch_events"] == 2

            print(
                json.dumps(
                    {
                        "ok": True,
                        "correlation_id": "corr-live-host-shape-e2e",
                        "workers": ["DESKTOP-PDQK954", "Noteri"],
                        "dispatch_1": "DESKTOP-PDQK954",
                        "dispatch_2_after_desktop_estudo": "Noteri",
                        "risk3": "human-gate-no-auto-dispatch",
                        "replay": "no-second-dispatch",
                        "independent_read": "passed",
                    },
                    sort_keys=True,
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
