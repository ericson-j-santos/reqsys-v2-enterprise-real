from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

import pytest

SERVER_PATH = Path("services/movimento-owner-gateway/server.py")
SERVER_SPEC = importlib.util.spec_from_file_location("owner_gateway_server", SERVER_PATH)
assert SERVER_SPEC and SERVER_SPEC.loader
server = importlib.util.module_from_spec(SERVER_SPEC)
SERVER_SPEC.loader.exec_module(server)

CLIENT_PATH = Path("scripts/movimento_owner_gateway_client.py")
CLIENT_SPEC = importlib.util.spec_from_file_location("owner_gateway_client", CLIENT_PATH)
assert CLIENT_SPEC and CLIENT_SPEC.loader
client = importlib.util.module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(client)


def test_detect_overlay_prefers_rfc6598(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_candidate_ipv4", lambda: ["192.168.1.10", "100.88.10.20", "127.0.0.1"])
    assert server.detect_overlay_ipv4() == "100.88.10.20"


def test_detect_overlay_fails_closed_without_private_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_candidate_ipv4", lambda: ["192.168.1.10", "127.0.0.1"])
    with pytest.raises(RuntimeError, match="private_overlay_ipv4_not_found"):
        server.detect_overlay_ipv4()


def test_gateway_bind_rejects_public_or_lan_address(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("x" * 40, encoding="utf-8")
    owner = tmp_path / "owner.py"
    owner.write_text("def validate(*a): return {'status':'passed'}\n", encoding="utf-8")
    config = {
        "logical_name": "reqsys-owner-data-gateway",
        "bind_ip": "192.168.1.20",
        "port": 18443,
        "token_file": str(token),
        "owner_module": str(owner),
        "runtime_dir": str(tmp_path),
        "source_db": "ReqSysMovimentoOwnerDev",
        "target_db": "ReqSysMovimentoDev",
    }
    with pytest.raises(RuntimeError, match="private_overlay_or_loopback"):
        server.OwnerGateway(config)


def test_load_config_requires_complete_contract(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"logical_name": "x"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="gateway_config_invalid"):
        server.load_config(path)


def test_client_requires_stable_logical_name(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("x" * 40, encoding="utf-8")
    path = tmp_path / "endpoint.json"
    path.write_text(json.dumps({
        "logical_name": "wrong",
        "host": "Noteri",
        "port": 18443,
        "token_file": str(token),
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="logical_name_mismatch"):
        client.load_endpoint(path)


def test_client_accepts_owner_gateway_descriptor(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("x" * 40, encoding="utf-8")
    path = tmp_path / "endpoint.json"
    path.write_text(json.dumps({
        "logical_name": "reqsys-owner-data-gateway",
        "host": "Noteri",
        "port": 18443,
        "token_file": str(token),
    }), encoding="utf-8")
    endpoint = client.load_endpoint(path)
    assert endpoint["logical_name"] == "reqsys-owner-data-gateway"
    assert endpoint["port"] == 18443


def test_token_digest_never_returns_plain_token() -> None:
    token = "a" * 48
    digest = server.token_digest(token)
    assert token not in digest
    assert len(digest) == 64
