from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_network_probe.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-network-probe.yml"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_network_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_rejects_non_noteri_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.validate_request("NO", "corr-runtime-surfaces")


def test_surfaces_are_fixed_and_read_only() -> None:
    assert probe.TARGET_HOST == "DESKTOP-PDQK954"
    assert probe.SURFACES == {
        "reqsys_dev_gateway": {"port": 8083, "path": "/api/health"},
        "codex_backend": {"port": 8000, "path": "/health"},
        "codex_gateway": {"port": 8008, "path": "/health"},
        "engineering_worker_pool": {"port": 8097, "path": "/health"},
        "engineering_orchestrator": {"port": 8787, "path": "/readyz"},
        "ollama": {"port": 11434, "path": "/api/tags"},
    }
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert 'parser.add_argument("--target"' not in raw
    assert 'method="get"' in raw
    assert "subprocess" not in raw
    assert "shell=true" not in raw


def test_forbidden_execution_surfaces_are_absent() -> None:
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    for marker in (
        "win32com",
        "openscmanager",
        "schtasks",
        "\\c$",
        "desktop_admin_broker",
        "remote desktop commander",
        "tailscale ssh",
        "paramiko",
        "winrm",
    ):
        assert marker not in raw


def test_probe_reports_only_sanitized_surface_state(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(
        probe,
        "probe_surfaces",
        lambda: {
            "reqsys_dev_gateway": {"port": 8083, "tcp_reachable": True, "http_status": 200},
            "codex_backend": {"port": 8000, "tcp_reachable": False, "http_status": None},
            "codex_gateway": {"port": 8008, "tcp_reachable": False, "http_status": None},
            "engineering_worker_pool": {"port": 8097, "tcp_reachable": False, "http_status": None},
            "engineering_orchestrator": {"port": 8787, "tcp_reachable": True, "http_status": 200},
            "ollama": {"port": 11434, "tcp_reachable": False, "http_status": None},
        },
    )
    result = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-001")
    assert result["ok"] is True
    assert result["open_surfaces"] == ["engineering_orchestrator", "reqsys_dev_gateway"]
    assert result["non_orchestrator_surfaces"] == ["reqsys_dev_gateway"]
    assert result["recovery_actuator_proven"] is False
    assert result["forbidden_transports_probed"] is False
    assert result["remote_shell_used"] is False
    assert result["credentials_supplied"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_only_orchestrator_does_not_prove_independent_actuator(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    states = {
        name: {
            "port": int(config["port"]),
            "tcp_reachable": name == "engineering_orchestrator",
            "http_status": 200 if name == "engineering_orchestrator" else None,
        }
        for name, config in probe.SURFACES.items()
    }
    monkeypatch.setattr(probe, "probe_surfaces", lambda: states)
    result = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-002")
    assert result["open_surfaces"] == ["engineering_orchestrator"]
    assert result["non_orchestrator_surfaces"] == []
    assert result["recovery_actuator_proven"] is False


def test_resolution_failure_does_not_probe_ports(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": False, "address_count": 0},
    )
    monkeypatch.setattr(
        probe,
        "probe_surfaces",
        lambda: (_ for _ in ()).throw(AssertionError("must not probe")),
    )
    result = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-003")
    assert result["dns_resolved"] is False
    assert result["open_surfaces"] == []
    assert result["non_orchestrator_surfaces"] == []
    assert result["recovery_actuator_proven"] is False


def test_workflow_remains_governed_and_noteri_only() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "session_launcher.py" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "2"' in raw
    assert '"--confirm", "PROBE-NOTERI-DESKTOP-NETWORK"' in raw


def test_evidence_payload_is_json_serializable(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": False, "address_count": 0},
    )
    payload = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-json")
    json.dumps(payload)
