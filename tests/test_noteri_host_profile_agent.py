from __future__ import annotations

import importlib.util
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "noteri_host_profile_agent.py"
SPEC = importlib.util.spec_from_file_location("noteri_host_profile_agent", MODULE_PATH)
assert SPEC and SPEC.loader
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


def _start_server(tmp_path: Path, *, allowed_origin: str = "http://localhost:5173"):
    profile = tmp_path / "host-profile.json"
    audit = tmp_path / "audit.jsonl"
    config = agent.AgentConfig(
        profile_path=profile,
        audit_path=audit,
        expected_host=socket.gethostname(),
        allowed_origins=frozenset({allowed_origin}),
    )
    server = agent.LocalAgentServer(("127.0.0.1", 0), agent.Handler)
    server.config = config
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, profile, audit


def _request(server, path: str, *, method: str = "GET", body=None, origin="http://localhost:5173"):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Origin": origin},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def test_agent_altera_estudo_e_confirma_leitura(tmp_path: Path):
    server, thread, profile, audit = _start_server(tmp_path)
    try:
        status, changed = _request(
            server,
            "/v1/profile",
            method="POST",
            body={
                "host": socket.gethostname(),
                "profile": "ESTUDO",
                "correlation_id": "corr-agent-estudo-001",
            },
        )
        assert status == 200
        assert changed["ok"] is True
        assert changed["profile"] == "ESTUDO"
        assert changed["accepts_new_development"] is False
        assert changed["changed"] is True

        status, readback = _request(server, "/v1/profile")
        assert status == 200
        assert readback["profile"] == "ESTUDO"
        assert readback["accepts_new_development"] is False
        assert profile.exists()
        rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["correlation_id"] == "corr-agent-estudo-001"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_agent_repeticao_e_idempotente(tmp_path: Path):
    server, thread, _, audit = _start_server(tmp_path)
    payload = {
        "host": socket.gethostname(),
        "profile": "ESTUDO",
        "correlation_id": "corr-agent-repeat-001",
    }
    try:
        _request(server, "/v1/profile", method="POST", body=payload)
        _, repeated = _request(
            server,
            "/v1/profile",
            method="POST",
            body={**payload, "correlation_id": "corr-agent-repeat-002"},
        )
        assert repeated["changed"] is False
        assert repeated["profile"] == "ESTUDO"
        assert len(audit.read_text(encoding="utf-8").splitlines()) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("body", "expected_fragment"),
    [
        ({"host": "outro-host", "profile": "ESTUDO", "correlation_id": "corr-invalid-host"}, "host_target_mismatch"),
        ({"host": socket.gethostname(), "profile": "INVALIDO", "correlation_id": "corr-invalid-profile"}, "NORMAL ou ESTUDO"),
        ({"host": socket.gethostname(), "profile": "NORMAL", "correlation_id": "short"}, "8..128"),
    ],
)
def test_agent_falha_fechado_para_entradas_invalidas(tmp_path: Path, body: dict, expected_fragment: str):
    server, thread, _, _ = _start_server(tmp_path)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(server, "/v1/profile", method="POST", body=body)
        payload = json.loads(exc.value.read().decode("utf-8"))
        assert exc.value.code in {409, 422}
        assert expected_fragment in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_agent_recusa_origin_nao_permitida(tmp_path: Path):
    server, thread, _, _ = _start_server(tmp_path)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(server, "/v1/profile", origin="https://origem-nao-permitida.example")
        assert exc.value.code == 403
        assert json.loads(exc.value.read().decode("utf-8"))["error"] == "origin_not_allowed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bind_externo_e_recusado(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["agent", "--bind", "0.0.0.0"],
    )
    assert agent.main() == 2
    assert "loopback" in capsys.readouterr().out
