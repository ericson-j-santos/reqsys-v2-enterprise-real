from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from orchestrator.core import COMPLETED, OrchestratorStore
from orchestrator.server import build_server


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


def main() -> None:
    correlation_id = "corr-http-e2e-001"
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "orchestrator.db"
        server = build_server("127.0.0.1", 0, db_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        try:
            status, created = call(
                "POST",
                base + "/v1/work-items",
                {
                    "event_id": "evt-http-e2e-001",
                    "correlation_id": correlation_id,
                    "idempotency_key": "reqsys:pr:1803",
                    "task_type": "ci failure remediation",
                    "payload": {"repository": "reqsys-v2-enterprise-real"},
                    "risk": 1,
                },
            )
            assert status == 201, (status, created)
            assert created["created"] is True
            assert created["item"]["target_worker"] == "ci-remediator"
            item_id = created["item"]["id"]

            status, replay = call(
                "POST",
                base + "/v1/work-items",
                {
                    "event_id": "evt-http-e2e-001",
                    "correlation_id": correlation_id,
                    "idempotency_key": "reqsys:pr:1803",
                    "task_type": "ci failure remediation",
                    "payload": {"repository": "reqsys-v2-enterprise-real"},
                    "risk": 1,
                },
            )
            assert status == 200, (status, replay)
            assert replay["replayed"] is True
            assert replay["item"]["id"] == item_id

            status, leased = call(
                "POST",
                base + "/v1/leases",
                {
                    "worker_role": "ci-remediator",
                    "worker_id": "worker-e2e-01",
                    "lease_seconds": 30,
                },
            )
            assert status == 200, (status, leased)
            assert leased["item"]["id"] == item_id

            status, rejected = call(
                "POST",
                base + f"/v1/work-items/{item_id}/complete",
                {
                    "worker_id": "wrong-worker",
                    "result": {"evidence": "must-not-be-written"},
                },
            )
            assert status == 409, (status, rejected)

            status, completed = call(
                "POST",
                base + f"/v1/work-items/{item_id}/complete",
                {
                    "worker_id": "worker-e2e-01",
                    "result": {"evidence": "e2e-http-ok"},
                },
            )
            assert status == 200, (status, completed)
            assert completed["item"]["status"] == COMPLETED

            status, invalid = call(
                "POST",
                base + "/v1/work-items",
                {
                    "event_id": "evt-http-negative-001",
                    "correlation_id": correlation_id,
                    "idempotency_key": "reqsys:negative:001",
                    "task_type": "implementation",
                    "payload": {"worker_hint": "untrusted-worker"},
                    "risk": 1,
                },
            )
            assert status == 400, (status, invalid)

            status, snapshot = call("GET", base + "/v1/status")
            assert status == 200, (status, snapshot)
            assert snapshot["total"] == 1, snapshot
            assert snapshot["by_status"][COMPLETED] == 1, snapshot

            independent = OrchestratorStore(db_path)
            persisted = independent.get(item_id)
            assert persisted is not None
            assert persisted.status == COMPLETED
            assert persisted.result == {"evidence": "e2e-http-ok"}
            assert independent.event_count() == 1

            print(
                json.dumps(
                    {
                        "ok": True,
                        "correlation_id": correlation_id,
                        "work_item_id": item_id,
                        "positive": "submit->lease->complete->independent-read",
                        "replay": "no duplicate",
                        "negative_control": "wrong lease owner and invalid worker rejected",
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
