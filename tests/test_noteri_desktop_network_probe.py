from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_network_probe.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-network-probe.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_network_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)



@pytest.fixture(autouse=True)
def no_real_control_plane_network(monkeypatch) -> None:
    monkeypatch.setattr(
        probe,
        "control_plane_probe",
        lambda: {"port_reachable": False, "http_status": None, "ready": False},
    )


def test_rejects_non_noteri_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.validate_request("NO", "corr-network-1234")


def test_resolution_failure_is_terminal_and_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": False, "address_count": 0},
    )
    result = probe.probe(probe.CONFIRM, "corr-network-resolution")
    assert result["ok"] is True
    assert result["probe_completed"] is True
    assert result["network_state"] == "name_resolution_failed"
    assert result["desktop_reachable"] is False
    assert "addresses" not in result
    assert result["secrets_read"] is False
    assert result["production_touched"] is False


def test_host_reachable_with_runtime_port_closed(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "icmp_reachable", lambda: True)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: False)
    result = probe.probe(probe.CONFIRM, "corr-network-host-up")
    assert result["desktop_reachable"] is True
    assert result["runtime_port_reachable"] is False
    assert result["network_state"] == "host_reachable_runtime_port_closed"


def test_runtime_port_proves_reachability(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "icmp_reachable", lambda: False)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: True)
    result = probe.probe(probe.CONFIRM, "corr-network-runtime")
    assert result["desktop_reachable"] is True
    assert result["runtime_port"] == 8081
    assert result["network_state"] == "runtime_port_reachable"


def test_control_plane_probe_is_reported_without_remote_mutation(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "icmp_reachable", lambda: True)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: False)
    monkeypatch.setattr(
        probe,
        "control_plane_probe",
        lambda: {"port_reachable": True, "http_status": 200, "ready": True},
    )
    result = probe.probe(probe.CONFIRM, "corr-control-plane-ready")
    assert result["control_plane_port"] == 8787
    assert result["control_plane_port_reachable"] is True
    assert result["control_plane_http_status"] == 200
    assert result["control_plane_ready"] is True
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_target_is_fixed_and_no_arbitrary_target_argument() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_HOST = "DESKTOP-PDQK954"' in content
    assert 'parser.add_argument("--target"' not in content
    assert "shell=True" not in content
    assert 'RUNTIME_PORT = 8081' in content
    assert 'CONTROL_PLANE_PORT = 8787' in content
    assert 'CONTROL_PLANE_PATH = "/readyz"' in content
    assert probe.ADMIN_STAGING_PATH == r"\\DESKTOP-PDQK954\C$\Users\Public\Desktop"


def test_workflow_is_noteri_only_and_inputless() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in content
    assert "--confirm PROBE-NOTERI-DESKTOP-NETWORK" in content
    assert "workflow_dispatch:" in content
    assert "inputs:" not in content
    assert "fix/noteri-desktop-network-probe-*" in content
    assert "shell: powershell" in content
    assert "shell: pwsh" not in content


def test_gateway_exposes_only_exact_network_probe_command() -> None:
    content = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run noteri-desktop-network-probe'" in content
    assert "'/reqsys run noteri-desktop-network-probe')" in content
    assert "target='noteri-desktop-network-probe.yml'" in content
    assert "steps.route.outputs.target == 'noteri-desktop-network-probe.yml'" in content
    assert "-f target=" not in content


def test_self_hosted_policy_explicitly_allows_probe() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-desktop-network-probe.yml" in policy["approved_workflows"]


def test_admin_staging_path_probe_accessible(monkeypatch) -> None:
    class FakeScan:
        def __enter__(self):
            return iter([object()])

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(probe.os, "scandir", lambda path: FakeScan())
    result = probe.admin_staging_path_probe()
    assert result == {"reachable": True, "result": "accessible"}


def test_admin_staging_path_probe_access_denied(monkeypatch) -> None:
    def denied(path):
        raise PermissionError("denied")

    monkeypatch.setattr(probe.os, "scandir", denied)
    result = probe.admin_staging_path_probe()
    assert result == {"reachable": False, "result": "access_denied"}


def test_probe_reports_smb_without_persisting_remote_listing(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(probe, "icmp_reachable", lambda: True)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: True)
    monkeypatch.setattr(
        probe,
        "admin_staging_path_probe",
        lambda: {"reachable": False, "result": "access_denied"},
    )
    result = probe.probe(probe.CONFIRM, "corr-network-smb")
    assert result["admin_staging_path_reachable"] is False
    assert result["admin_staging_path_result"] == "access_denied"
    assert result["admin_staging_path"] == r"C:\Users\Public\Desktop"
    assert "listing" not in result
    assert "files" not in result
