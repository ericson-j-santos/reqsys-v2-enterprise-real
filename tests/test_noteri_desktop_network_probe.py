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
        "docker_engine_http": {"port": 2375, "path": "/version"},
        "docker_engine_tls": {"port": 2376, "path": None},
    }
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert 'parser.add_argument("--target"' not in raw
    assert 'method="get"' in raw
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
            "docker_engine_http": {"port": 2375, "tcp_reachable": False, "http_status": None},
            "docker_engine_tls": {"port": 2376, "tcp_reachable": False, "http_status": None},
        },
    )
    monkeypatch.setattr(
        probe,
        "probe_visible_smb_shares",
        lambda: {"status": "accessible", "visible_share_count": 1},
    )
    result = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-001")
    assert result["ok"] is True
    assert result["open_surfaces"] == ["engineering_orchestrator", "reqsys_dev_gateway"]
    assert result["non_orchestrator_surfaces"] == ["reqsys_dev_gateway"]
    assert result["smb_non_admin_transport_candidate"] is True
    assert result["docker_remote_api_candidate"] is False
    assert result["remote_write_attempted"] is False
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
    monkeypatch.setattr(
        probe,
        "probe_visible_smb_shares",
        lambda: {"status": "accessible", "visible_share_count": 0},
    )
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

def test_visible_smb_share_probe_is_read_only_and_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(probe, "system32_executable", lambda name: Path(r"C:\Windows\System32\net.exe"))
    observed = {}

    class Completed:
        returncode = 0
        stdout = (
            "Shared resources at \\\\DESKTOP-PDQK954\n\n"
            "Share name   Type  Used as  Comment\n"
            "-------------------------------------\n"
            "Public       Disk\n"
            "The command completed successfully.\n"
        )
        stderr = ""

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    result = probe.probe_visible_smb_shares()
    assert result == {"status": "accessible", "visible_share_count": 1}
    assert observed["args"] == [
        r"C:\Windows\System32\net.exe",
        "view",
        r"\\DESKTOP-PDQK954",
    ]
    assert observed["kwargs"]["shell"] is False
    assert "Public" not in json.dumps(result)


def test_docker_http_candidate_never_proves_recovery(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    states = {
        name: {
            "port": int(config["port"]),
            "tcp_reachable": name == "docker_engine_http",
            "http_status": 200 if name == "docker_engine_http" else None,
        }
        for name, config in probe.SURFACES.items()
    }
    monkeypatch.setattr(probe, "probe_surfaces", lambda: states)
    monkeypatch.setattr(
        probe,
        "probe_visible_smb_shares",
        lambda: {"status": "unavailable", "visible_share_count": 0},
    )
    result = probe.probe(probe.CONFIRM, "corr-runtime-surfaces-docker")
    assert result["docker_remote_api_candidate"] is True
    assert result["recovery_actuator_proven"] is False
    assert result["remote_write_attempted"] is False
