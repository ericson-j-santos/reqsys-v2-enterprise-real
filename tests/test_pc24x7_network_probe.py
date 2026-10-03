from __future__ import annotations

import json
import socket
import threading
import time

from scripts import pc24x7_network_probe as probe


def test_safe_ipv4_filters_loopback_linklocal_and_duplicates() -> None:
    assert probe._safe_ipv4(
        ["127.0.0.1", "169.254.10.1", "192.168.10.20", "192.168.10.20", "10.0.0.8"]
    ) == ["10.0.0.8", "192.168.10.20"]


def test_resolve_ipv4_uses_only_ipv4(monkeypatch) -> None:
    monkeypatch.setattr(
        probe.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ],
    )
    assert probe.resolve_ipv4("desktop") == ["192.168.1.10"]


def test_connect_once_real_loopback_handshake() -> None:
    marker = "cwp-network-test"
    holder: dict[str, object] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserver:
        reserver.bind(("127.0.0.1", 0))
        port = reserver.getsockname()[1]

    def server() -> None:
        holder["result"] = probe.serve_once("127.0.0.1", port, marker, 3.0)

    thread = threading.Thread(target=server, daemon=True)
    thread.start()

    last_error: Exception | None = None
    for _ in range(20):
        try:
            result = probe.connect_once("127.0.0.1", port, marker, 1.0)
            break
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    else:
        raise AssertionError(f"listener não iniciou: {last_error}")

    thread.join(timeout=3)
    assert result["ok"] is True
    assert result["marker_matched"] is True
    assert holder["result"]["ok"] is True


def test_connect_rejects_wrong_marker() -> None:
    expected = "expected-marker"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserver:
        reserver.bind(("127.0.0.1", 0))
        port = reserver.getsockname()[1]

    thread = threading.Thread(
        target=probe.serve_once,
        args=("127.0.0.1", port, expected, 3.0),
        daemon=True,
    )
    thread.start()

    for _ in range(20):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0) as client:
                client.sendall(b"wrong-marker\n")
                payload = json.loads(client.recv(2048).decode("utf-8"))
            break
        except OSError:
            time.sleep(0.05)
    else:
        raise AssertionError("listener não iniciou")

    thread.join(timeout=3)
    assert payload["ok"] is False
    assert payload["marker_matched"] is False
