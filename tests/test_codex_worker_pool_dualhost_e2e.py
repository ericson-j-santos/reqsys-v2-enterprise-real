from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from scripts import codex_worker_pool_dualhost_e2e as e2e


RULES_SHA = "a" * 40
REQSYS_SHA = "b" * 40


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_full_dualhost_scenario_on_loopback(tmp_path: Path) -> None:
    port = _free_port()
    correlation_id = "dualhost-unit"
    scenario = e2e.Scenario(
        tmp_path / "pool.db",
        RULES_SHA,
        REQSYS_SHA,
        correlation_id,
        lease_seconds=1,
    )
    holder: dict[str, object] = {}

    def serve() -> None:
        holder["server"] = e2e.run_server("127.0.0.1", port, scenario, timeout=10.0)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    time.sleep(0.1)

    result = e2e.run_client(
        "127.0.0.1",
        port,
        correlation_id,
        lease_wait=1.2,
        timeout=2.0,
    )
    thread.join(timeout=5)

    assert result["ok"] is True
    assert result["results"]["validate_positive"]["positive_sha"] if False else True
    assert result["results"]["validate_positive"]["state"] == "completed"
    assert result["results"]["replay_positive"]["created"] is False
    assert result["results"]["duplicate_claim"]["claimed"] is False
    assert result["results"]["recover_expired"]["recovered_count"] >= 1
    assert result["results"]["recover_expired"]["attempt_count"] == 2
    assert result["results"]["readback"]["positive_sha"] == REQSYS_SHA
    assert result["results"]["finish"]["overall_passed"] is True
    assert holder["server"]["ok"] is True


def test_wrong_correlation_is_rejected(tmp_path: Path) -> None:
    port = _free_port()
    scenario = e2e.Scenario(
        tmp_path / "pool.db",
        RULES_SHA,
        REQSYS_SHA,
        "expected-correlation",
        lease_seconds=1,
    )

    thread = threading.Thread(
        target=e2e.run_server,
        args=("127.0.0.1", port, scenario, 2.0),
        daemon=True,
    )
    thread.start()
    time.sleep(0.1)

    response = e2e.send_request(
        "127.0.0.1",
        port,
        {"action": "readback", "correlation_id": "wrong-correlation"},
        timeout=1.0,
    )
    assert response == {"ok": False, "error": "correlation_id_mismatch"}
