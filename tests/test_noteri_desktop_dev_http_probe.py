from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_dev_http_probe.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-network-probe.yml"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_dev_http_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_contract_is_fixed_to_noteri_desktop_dev_http() -> None:
    assert probe.EXPECTED_HOST == "Noteri"
    assert probe.TARGET_HOST == "DESKTOP-PDQK954"
    assert probe.DEV_GATEWAY_PORT == 8083
    assert probe.ALLOWED_PATHS == ("/api/health", "/api/runtime/health")
    source = SCRIPT.read_text(encoding="utf-8").casefold()
    assert "subprocess" not in source
    assert "win32com" not in source
    assert "scandir" not in source
    assert "shell=true" not in source


def test_rejects_non_noteri_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.validate_request("NO", "corr-http-1234")


def test_rejects_non_allowlisted_http_path() -> None:
    with pytest.raises(probe.ProbeError, match="path HTTP não autorizado"):
        probe.http_status("/admin/recover")


def test_probe_uses_only_dev_http_route(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "tcp_reachable", lambda: True)

    observed: list[str] = []

    def fake_http(path: str):
        observed.append(path)
        return {
            "transport_reachable": True,
            "status": 200 if path == "/api/health" else 503,
            "error_type": None,
        }

    monkeypatch.setattr(probe, "http_status", fake_http)
    result = probe.probe(probe.CONFIRM, "corr-dev-http-route")

    assert observed == list(probe.ALLOWED_PATHS)
    assert result["route"] == "reqsys_dev_http_8083"
    assert result["target_port"] == 8083
    assert result["network_state"] == "dev_gateway_http_reachable"
    assert result["candidate_transport_reachable"] is True
    assert result["http_probes"]["/api/health"]["status"] == 200
    assert result["http_probes"]["/api/runtime/health"]["status"] == 503
    assert result["excluded_routes"] == ["wmi", "scm", "schtasks", "c$", "admin_broker"]
    assert result["rdc_required"] is False
    assert result["remote_shell_used"] is False
    assert result["credentials_supplied"] is False
    assert result["mutating_request_sent"] is False
    assert result["uac_or_acl_relaxed"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_closed_port_is_terminal_diagnostic(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "tcp_reachable", lambda: False)
    monkeypatch.setattr(
        probe,
        "http_status",
        lambda path: pytest.fail("HTTP não deve ser tentado com TCP fechado"),
    )

    result = probe.probe(probe.CONFIRM, "corr-dev-http-closed")
    assert result["network_state"] == "dev_gateway_tcp_closed"
    assert result["candidate_transport_reachable"] is False
    assert all(
        value["error_type"] == "not_attempted"
        for value in result["http_probes"].values()
    )


def test_workflow_executes_only_new_http_probe() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/noteri_desktop_dev_http_probe.py" in raw
    assert "tests/test_noteri_desktop_dev_http_probe.py" in raw
    assert "PROBE-NOTERI-DESKTOP-DEV-HTTP" in raw
    assert "scripts/noteri_desktop_network_probe.py" not in raw
    assert "tests/test_noteri_desktop_network_probe.py" not in raw
    assert "session_launcher.py" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "2"' in raw

# E2E branch trigger: HTTP-only route.
