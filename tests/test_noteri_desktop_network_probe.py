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


def test_rejects_non_noteri_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.validate_request("NO", "corr-network-1234")


def _base_probe(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(
        probe,
        "resolve_target",
        lambda: {"resolved": True, "address_count": 1},
    )
    monkeypatch.setattr(
        probe,
        "admin_staging_path_probe",
        lambda: {"reachable": False, "result": "access_denied"},
    )
    monkeypatch.setattr(
        probe,
        "wmi_readonly_probe",
        lambda: {
            "reachable": False,
            "result": "access_denied",
            "stage": "connect_server",
            "error_type": "com_error",
            "hresult": "0x80070005",
            "namespace": probe.WMI_NAMESPACE,
            "query_class": probe.WMI_QUERY_CLASS,
        },
    )


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
    assert result["wmi_result"] == "not_attempted"
    assert "addresses" not in result
    assert result["secrets_read"] is False
    assert result["production_touched"] is False


def test_host_reachable_with_runtime_port_closed(monkeypatch) -> None:
    _base_probe(monkeypatch)
    monkeypatch.setattr(probe, "icmp_reachable", lambda: True)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: False)
    result = probe.probe(probe.CONFIRM, "corr-network-host-up")
    assert result["desktop_reachable"] is True
    assert result["runtime_port_reachable"] is False
    assert result["network_state"] == "host_reachable_runtime_port_closed"


def test_runtime_port_proves_reachability(monkeypatch) -> None:
    _base_probe(monkeypatch)
    monkeypatch.setattr(probe, "icmp_reachable", lambda: False)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: True)
    result = probe.probe(probe.CONFIRM, "corr-network-runtime")
    assert result["desktop_reachable"] is True
    assert result["runtime_port"] == 8081
    assert result["network_state"] == "runtime_port_reachable"


def test_wmi_can_independently_prove_reachability(monkeypatch) -> None:
    _base_probe(monkeypatch)
    monkeypatch.setattr(probe, "icmp_reachable", lambda: False)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: False)
    monkeypatch.setattr(
        probe,
        "wmi_readonly_probe",
        lambda: {
            "reachable": True,
            "result": "accessible",
            "stage": "completed",
            "error_type": None,
            "hresult": None,
            "namespace": probe.WMI_NAMESPACE,
            "query_class": probe.WMI_QUERY_CLASS,
        },
    )
    result = probe.probe(probe.CONFIRM, "corr-network-wmi")
    assert result["desktop_reachable"] is True
    assert result["wmi_reachable"] is True
    assert result["network_state"] == "host_reachable_wmi_runtime_port_closed"


def test_target_is_fixed_and_no_arbitrary_target_argument() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_HOST = "DESKTOP-PDQK954"' in content
    assert 'parser.add_argument("--target"' not in content
    assert "shell=True" not in content
    assert 'RUNTIME_PORT = 8081' in content
    assert probe.ADMIN_STAGING_PATH == r"\\DESKTOP-PDQK954\C$\Users\Public\Desktop"


def test_wmi_contract_is_read_only_and_credential_free() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    assert 'WMI_NAMESPACE = r"root\\cimv2"' in content
    assert 'WMI_QUERY_CLASS = "Win32_OperatingSystem"' in content
    assert "ConnectServer(TARGET_HOST, WMI_NAMESPACE)" in content
    assert "ExecQuery(WMI_QUERY" in content
    assert "Win32_Process.Create" not in content
    assert "username" not in content.casefold()
    assert "password" not in content.casefold()


def test_wmi_access_denied_is_sanitized(monkeypatch) -> None:
    class FakeComError(Exception):
        hresult = -2147024891

    class PythonCom:
        @staticmethod
        def CoInitialize():
            return None

        @staticmethod
        def CoUninitialize():
            return None

    class Client:
        @staticmethod
        def Dispatch(name):
            class Locator:
                def ConnectServer(self, host, namespace):
                    raise FakeComError("sensitive-detail-must-not-leak")
            return Locator()

    monkeypatch.setattr(probe, "_wmi_client", lambda: (PythonCom, Client))
    result = probe.wmi_readonly_probe()
    assert result["reachable"] is False
    assert result["result"] == "access_denied"
    assert result["stage"] == "connect_server"
    assert result["hresult"] == "0x80070005"
    assert "error" not in result


def test_wmi_accessible_returns_only_sanitized_metadata(monkeypatch) -> None:
    class PythonCom:
        @staticmethod
        def CoInitialize():
            return None

        @staticmethod
        def CoUninitialize():
            return None

    class Security:
        ImpersonationLevel = 0

    class Services:
        Security_ = Security()

        def ExecQuery(self, query, language, flags):
            assert query == probe.WMI_QUERY
            assert language == "WQL"
            return [object()]

    class Client:
        @staticmethod
        def Dispatch(name):
            assert name == "WbemScripting.SWbemLocator"

            class Locator:
                def ConnectServer(self, host, namespace):
                    assert host == probe.TARGET_HOST
                    assert namespace == probe.WMI_NAMESPACE
                    return Services()

            return Locator()

    monkeypatch.setattr(probe, "_wmi_client", lambda: (PythonCom, Client))
    result = probe.wmi_readonly_probe()
    assert result == {
        "reachable": True,
        "result": "accessible",
        "stage": "completed",
        "error_type": None,
        "hresult": None,
        "namespace": r"root\cimv2",
        "query_class": "Win32_OperatingSystem",
    }


def test_workflow_is_noteri_only_inputless_and_governed() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in content
    assert '"--confirm", "PROBE-NOTERI-DESKTOP-NETWORK"' in content
    assert "workflow_dispatch:" in content
    assert "inputs:" not in content
    assert "fix/noteri-desktop-network-probe-*" in content
    assert "session_launcher.py" in content
    assert "command_gateway.py" in content
    assert '"--risk", "2"' in content
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


def test_probe_reports_smb_and_wmi_without_sensitive_remote_data(monkeypatch) -> None:
    _base_probe(monkeypatch)
    monkeypatch.setattr(probe, "icmp_reachable", lambda: True)
    monkeypatch.setattr(probe, "runtime_port_reachable", lambda: True)
    result = probe.probe(probe.CONFIRM, "corr-network-sanitized")
    assert result["admin_staging_path_result"] == "access_denied"
    assert result["wmi_result"] == "access_denied"
    assert result["wmi_query_class"] == "Win32_OperatingSystem"
    assert "listing" not in result
    assert "files" not in result
    assert result["remote_shell_used"] is False
    assert result["credentials_supplied"] is False


def test_nested_rpc_hresult_is_classified() -> None:
    exc = RuntimeError("outer", (-2147023174, "inner"))
    assert probe._classify_wmi_error(exc) == "rpc_server_unavailable"
    assert probe._safe_hresult(exc) == "0x800706BA"
