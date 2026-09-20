from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from orchestrator.core import BLOCKED, COMPLETED, OrchestratorStore
from orchestrator.persistence import backup_database
from orchestrator.server import build_server
from orchestrator.worker_agent import WorkerAgent, WorkerAgentConfig, request_json


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "orchestrator.db"
        backup = root / "orchestrator.backup.db"
        profile = root / "host-profile.json"
        profile.write_text(json.dumps({"profile": "NORMAL"}), encoding="utf-8")

        server = build_server("127.0.0.1", 0, db)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}"

        agent = WorkerAgent(
            WorkerAgentConfig(
                endpoint=endpoint,
                worker_id="worker-e2e",
                roles=["builder", "ci-remediator", "e2e-validator"],
                controller_version="e2e",
                dispatch_priority=1,
                heartbeat_ttl_seconds=120,
                heartbeat_interval_seconds=5,
                poll_interval_seconds=0.1,
                lease_seconds=120,
                profile_path=profile,
            )
        )

        try:
            agent.heartbeat("corr-executor-heartbeat")

            status, created = request_json(
                "POST",
                endpoint + "/v1/intake",
                {
                    "event_id": "evt-executor-positive",
                    "correlation_id": "corr-executor-positive",
                    "idempotency_key": "executor:positive",
                    "task_type": "orchestrator.selftest",
                    "payload": {"input": "physical-ready"},
                    "risk": 1,
                    "max_attempts": 1,
                    "lease_seconds": 120,
                },
            )
            assert status == 201, (status, created)
            item_id = created["item"]["id"]
            outcome = agent.process_one()
            assert outcome and outcome["status"] == "completed", outcome

            independent = OrchestratorStore(db)
            item = independent.get(item_id)
            assert item is not None
            assert item.status == COMPLETED
            assert item.result["worker_id"] == "worker-e2e"
            assert item.result["input"] == "physical-ready"

            status, negative = request_json(
                "POST",
                endpoint + "/v1/intake",
                {
                    "event_id": "evt-executor-negative",
                    "correlation_id": "corr-executor-negative",
                    "idempotency_key": "executor:negative",
                    "task_type": "implementation",
                    "payload": {},
                    "risk": 1,
                    "max_attempts": 1,
                    "lease_seconds": 120,
                },
            )
            assert status == 201, (status, negative)
            negative_id = negative["item"]["id"]
            failed = agent.process_one()
            assert failed and failed["status"] == "failed", failed
            negative_item = independent.get(negative_id)
            assert negative_item is not None
            assert negative_item.status == BLOCKED
            assert "unsupported task_type" in negative_item.last_error

            backup_database(db, backup)
            backup_store = OrchestratorStore(backup)
            persisted = backup_store.get(item_id)
            assert persisted is not None
            assert persisted.status == COMPLETED

            status, ready = request_json("GET", endpoint + "/readyz")
            assert status == 200 and ready["ready"] is True

            print(
                json.dumps(
                    {
                        "ok": True,
                        "positive": "lease->renew->allowlisted-handler->complete",
                        "negative": "unsupported-handler->blocked",
                        "backup": "online-backup-independent-read",
                        "readyz": True,
                        "correlation_id": "corr-executor-positive",
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
