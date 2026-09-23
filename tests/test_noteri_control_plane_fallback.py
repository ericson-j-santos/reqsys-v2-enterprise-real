from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts" / "noteri_control_plane_probe.py"
WATCHDOG_PATH = ROOT / "scripts" / "noteri_control_plane_watchdog.py"
WORKFLOW = ROOT / ".github/workflows/noteri-control-plane-probe.yml"
HEADLESS_WORKFLOW = ROOT / ".github/workflows/noteri-headless-control-plane-activation.yml"
HEADLESS_LAUNCHER = ROOT / "scripts" / "noteri_control_plane_watchdog_uac_launcher.py"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"

PROBE_SPEC = importlib.util.spec_from_file_location("noteri_control_plane_probe", PROBE_PATH)
assert PROBE_SPEC and PROBE_SPEC.loader
probe = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(probe)

WATCHDOG_SPEC = importlib.util.spec_from_file_location("noteri_control_plane_watchdog", WATCHDOG_PATH)
assert WATCHDOG_SPEC and WATCHDOG_SPEC.loader
watchdog = importlib.util.module_from_spec(WATCHDOG_SPEC)
WATCHDOG_SPEC.loader.exec_module(watchdog)


def test_probe_rejects_other_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_probe_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.probe("NO", "corr-12345678")


def test_probe_parses_headless_task_xml() -> None:
    raw = b"""<?xml version="1.0" encoding="UTF-8"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals><Principal><LogonType>S4U</LogonType></Principal></Principals>
  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
  <Settings><Enabled>true</Enabled></Settings>
</Task>
"""
    task = probe.parse_task_xml(raw)
    assert task == {
        "exists": True,
        "enabled": True,
        "trigger_at_startup": True,
        "logon_type": "S4U",
        "validator": "schtasks_xml",
    }
    assert probe.task_headless_ready(task) is True


def test_probe_proves_runner_without_rdc(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(probe, "runner_listener_detected", lambda: True)
    monkeypatch.setattr(
        probe,
        "task_status",
        lambda: {
            "exists": True,
            "enabled": True,
            "trigger_at_startup": True,
            "logon_type": "S4U",
            "validator": "schtasks_xml",
        },
    )
    monkeypatch.setattr(
        probe,
        "activation_diagnostic",
        lambda: {
            "interactive": {"exists": False},
            "elevated": {"exists": False},
        },
    )
    monkeypatch.setenv("RUNNER_NAME", "noteri-reqsys-dev")
    monkeypatch.setenv("RUNNER_OS", "Windows")
    monkeypatch.setenv("RUNNER_ARCH", "X64")
    result = probe.probe(probe.CONFIRM, "corr-noteri-probe")
    assert result["ok"] is True
    assert result["host"] == "Noteri"
    assert result["runner_listener_detected"] is True
    assert result["headless_ready"] is True
    assert result["headless_task"]["trigger_at_startup"] is True
    assert result["headless_task"]["logon_type"] == "S4U"
    assert result["rdc_required"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_probe_sanitizes_activation_diagnostics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "ReqSys" / "NoteriControlPlaneWatchdog"
    root.mkdir(parents=True)
    (root / "interactive-launch-result.json").write_text(
        json.dumps(
            {
                "ok": False,
                "exit_code": 2,
                "source_sha": "a" * 40,
                "result": "interactive_launcher_exception",
                "error_type": "RuntimeError",
                "error": "falha controlada",
                "observed_at": "2026-09-21T00:00:00+00:00",
                "secret": "never-expose",
            }
        ),
        encoding="utf-8",
    )
    (root / "elevated-install-result.json").write_text(
        json.dumps(
            {
                "ok": False,
                "error_type": "WatchdogError",
                "error": "registro falhou",
                "runtime_ok": True,
                "activation_pending": True,
                "requires_uac_activation": True,
                "headless_persistence": False,
                "principal": "must-not-leak",
            }
        ),
        encoding="utf-8",
    )

    result = probe.activation_diagnostic()
    assert result["interactive"]["exists"] is True
    assert result["interactive"]["exit_code"] == 2
    assert "secret" not in result["interactive"]
    assert result["elevated"]["activation_pending"] is True
    assert "principal" not in result["elevated"]


def test_watchdog_runner_contract_never_reads_runner_contents(tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("sensitive-placeholder", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")
    assert watchdog.validate_runner_home(root) == root.resolve()


def test_watchdog_cycle_starts_runner_when_listener_missing(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("opaque", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")
    observed = iter([False, True])
    monkeypatch.setattr(watchdog, "require_noteri", lambda: "Noteri")
    monkeypatch.setattr(watchdog, "runner_running", lambda: next(observed))
    monkeypatch.setattr(watchdog, "start_runner", lambda path: True)
    monkeypatch.setattr(watchdog, "runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr(watchdog, "atomic_json", lambda path, payload: None)
    result = watchdog.cycle(root)
    assert result["ok"] is True
    assert result["runner_start_attempted"] is True
    assert result["runner_started"] is True
    assert result["rdc_required"] is False


def test_workflow_and_policy_are_fixed_to_noteri() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "--confirm PROBE-NOTERI-CONTROL-PLANE" in workflow
    assert "shell: powershell" in workflow
    assert "shell: pwsh" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "inputs:" not in workflow
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-control-plane-probe.yml" in policy["approved_workflows"]


def test_watchdog_installs_hkcu_fallback_when_startup_task_denied(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("opaque", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")

    repo_root = tmp_path / "repo"
    scripts = repo_root / "scripts"
    scripts.mkdir(parents=True)
    source = scripts / "noteri_control_plane_watchdog.py"
    source.write_text(WATCHDOG_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(watchdog, "require_noteri", lambda: "Noteri")
    monkeypatch.setattr(watchdog, "runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr(
        watchdog,
        "register_task",
        lambda **kwargs: (_ for _ in ()).throw(PermissionError("Access is denied")),
    )
    monkeypatch.setattr(
        watchdog,
        "install_logon_fallback",
        lambda **kwargs: {
            "exists": True,
            "trigger": "AtLogon",
            "scope": "HKCU",
            "headless": False,
        },
    )
    monkeypatch.setattr(
        watchdog,
        "cycle",
        lambda runner_home: {"ok": True, "runner_running_after": True},
    )

    result = watchdog.install(
        repo_root,
        root,
        "a" * 40,
        watchdog.INSTALL_CONFIRM,
    )
    assert result["runtime_ok"] is True
    assert result["activation_pending"] is True
    assert result["runtime_persistent_after_login"] is True
    assert result["headless_persistence"] is False
    assert result["logon_fallback"]["scope"] == "HKCU"


def test_headless_activation_workflow_is_fixed_to_noteri_and_uac() -> None:
    workflow = HEADLESS_WORKFLOW.read_text(encoding="utf-8")
    launcher = HEADLESS_LAUNCHER.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "shell: powershell" in workflow
    assert "shell: pwsh" not in workflow
    assert "--confirm LAUNCH-NOTERI-CONTROL-PLANE-WATCHDOG-UAC" in workflow
    assert "workflow_dispatch:" in workflow
    assert "Ativar-Noteri-Headless.ps1" in workflow
    assert "Ativar-Noteri-Headless.cmd" in workflow
    assert "[Environment]::GetFolderPath('Desktop')" in workflow
    assert "ExecutionPolicy Bypass -File" in workflow
    assert "NoteriControlPlaneBootstrap" in workflow
    assert "Copy-Item" in workflow
    assert "Get-FileHash" in workflow
    assert "NOTERI_IMMUTABLE_SOURCE_SHA" in workflow
    assert "Get-Command python -ErrorAction Stop" in workflow
    assert "interactive-launch-result.json" in workflow
    assert "remote_uac_attempted = $false" in workflow
    assert "Request governed UAC and validate headless task" not in workflow
    assert "origin/main" not in workflow
    assert "git -C $p fetch origin main" not in workflow
    assert "inputs:" not in workflow
    assert "ShellExecuteW" in launcher
    assert "--result-path" in launcher
    assert "ELEVATED_INSTALL_FAILED" in launcher
    assert "schtasks.exe" in launcher
    assert "schtasks_xml" in launcher
    assert '"runas"' in launcher
    assert 'EXPECTED_HOST' not in launcher or "watchdog.EXPECTED_HOST" in launcher
    assert "AtStartup" in launcher or "trigger_at_startup" in launcher
    assert "s4u" in launcher.casefold()
    assert "reboot_performed" in launcher
    assert ".github/workflows/noteri-headless-control-plane-activation.yml" in policy["approved_workflows"]


def test_watchdog_creates_automation_folder_when_missing() -> None:
    class Root:
        def __init__(self) -> None:
            self.created = None

        def CreateFolder(self, name: str):
            self.created = name
            return {"folder": name}

    class Service:
        def __init__(self) -> None:
            self.root = Root()

        def GetFolder(self, path: str):
            if path == "\\":
                return self.root
            raise RuntimeError("missing")

    service = Service()
    folder = watchdog.ensure_task_folder(service)
    assert folder == {"folder": "Automation"}
    assert service.root.created == "Automation"


def test_headless_launcher_uses_only_legitimate_uac_brokers() -> None:
    launcher = HEADLESS_LAUNCHER.read_text(encoding="utf-8")
    assert "ShellExecuteW" in launcher
    assert "Start-Process" in launcher
    assert "-Verb RunAs" in launcher
    assert "Shell.Application" in launcher
    assert "powershell_start_process_runas" in launcher
    assert "shell_application_runas" in launcher
    assert "fodhelper" not in launcher.casefold()
    assert "computerdefaults" not in launcher.casefold()
    assert "eventvwr" not in launcher.casefold()


def test_watchdog_resolves_current_windows_principal_for_s4u() -> None:
    text = WATCHDOG_PATH.read_text(encoding="utf-8")
    assert "whoami.exe" in text
    assert '"/user", "/fo", "csv", "/nh"' in text
    assert 'candidates.append(("sid", sid))' in text
    assert 'candidates.append(("whoami", account))' in text
    assert "principal_source" in text
    assert 'f"{socket.gethostname()}\\\\{os.environ.get(' not in text


def test_watchdog_extracts_nested_task_scheduler_hresult() -> None:
    exc = RuntimeError(
        -2147352567,
        "Exception occurred.",
        (0, None, None, None, 0, -2147023570),
        None,
    )
    assert watchdog._exception_hresults(exc) == [-2147023570]
    assert watchdog._hresult_label(-2147023570) == "0x8007052E"


def test_watchdog_task_contract_requires_boot_s4u(monkeypatch) -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals><Principal><LogonType>S4U</LogonType></Principal></Principals>
  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
  <Settings><Enabled>true</Enabled></Settings>
</Task>
"""

    class Completed:
        returncode = 0
        stdout = xml

    monkeypatch.setattr(watchdog, "schtasks_path", lambda: Path("schtasks.exe"))
    monkeypatch.setattr(watchdog.subprocess, "run", lambda *args, **kwargs: Completed())
    task = watchdog.task_contract()
    assert watchdog.task_contract_ready(task) is True
    assert task["logon_type"] == "S4U"
    assert "principal" not in task


def test_watchdog_native_s4u_fallback_uses_np_without_password(monkeypatch, tmp_path: Path) -> None:
    observed: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        observed.append([str(item) for item in argv])
        return Completed()

    monkeypatch.setattr(watchdog, "schtasks_path", lambda: Path("schtasks.exe"))
    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    monkeypatch.setattr(
        watchdog,
        "_validate_registered_task",
        lambda method, source: {
            "exists": True,
            "trigger": "AtStartup",
            "logon": "S4U",
            "registration_method": method,
            "principal_source": source,
        },
    )
    result, failures = watchdog._register_schtasks_np(
        python_executable="python.exe",
        release_script=tmp_path / "watchdog.py",
        runner_home=tmp_path / "runner",
        candidates=[("whoami", r"NOTERI\user")],
    )
    assert failures == []
    assert result is not None
    assert result["registration_method"] == "schtasks_np"
    argv = observed[0]
    assert "/NP" in argv
    assert "/SC" in argv and "ONSTART" in argv
    assert "/RL" in argv and "LIMITED" in argv
    assert "/RP" not in argv
    assert "/RU" not in argv


def test_watchdog_register_task_falls_back_from_com_to_native(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(watchdog, "_scheduler", lambda: object())
    monkeypatch.setattr(watchdog, "ensure_task_folder", lambda service: object())
    monkeypatch.setattr(
        watchdog,
        "current_principal_candidates",
        lambda: [("whoami", r"NOTERI\user")],
    )
    monkeypatch.setattr(
        watchdog,
        "_register_com_s4u",
        lambda *args, **kwargs: (None, ["whoami/explicit_null_password:0x8007052E"]),
    )
    monkeypatch.setattr(
        watchdog,
        "_register_schtasks_np",
        lambda *args, **kwargs: (
            {
                "exists": True,
                "trigger": "AtStartup",
                "logon": "S4U",
                "registration_method": "schtasks_np",
                "principal_source": "current_user",
            },
            [],
        ),
    )
    result = watchdog.register_task(
        python_executable="python.exe",
        release_script=tmp_path / "watchdog.py",
        runner_home=tmp_path / "runner",
    )
    assert result["registration_method"] == "schtasks_np"
    assert result["logon"] == "S4U"


def test_watchdog_s4u_registration_never_embeds_password() -> None:
    text = WATCHDOG_PATH.read_text(encoding="utf-8")
    assert '"/NP"' in text
    assert '"/RP"' not in text
    assert "explicit_null_password" in text
    assert "0x8007052E" not in text


def test_probe_runner_registry_uses_local_gh_without_workflow_token(monkeypatch) -> None:
    observed = []

    class Completed:
        def __init__(self, returncode=0, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(argv, **kwargs):
        observed.append((list(argv), dict(kwargs.get("env") or {})))
        if argv[2:4] == ["user", "--jq"]:
            return Completed(stdout="ericson-j-santos\n")
        return Completed(
            stdout=json.dumps(
                {
                    "runners": [
                        {
                            "name": "DESKTOP-PDQK954",
                            "status": "offline",
                            "busy": False,
                            "labels": [
                                {"name": "self-hosted"},
                                {"name": "Windows"},
                                {"name": "X64"},
                                {"name": "pc24x7"},
                                {"name": "reqsys-dev"},
                            ],
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(probe.shutil, "which", lambda name: r"C:\Program Files\GitHub CLI\gh.exe")
    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    monkeypatch.setenv("GH_TOKEN", "must-not-be-used")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-be-used")

    result = probe.github_runner_registry_probe()
    assert result["ok"] is True
    assert result["admin_access"] is True
    assert result["runner_status"] == "offline"
    assert result["runner_labels"] == ["Windows", "X64", "pc24x7", "reqsys-dev", "self-hosted"]
    assert all("GH_TOKEN" not in env and "GITHUB_TOKEN" not in env for _, env in observed)


def test_probe_runner_registry_reports_access_denied_without_secret_leak(monkeypatch) -> None:
    class Completed:
        def __init__(self, returncode=0, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = "sensitive detail"

    calls = iter([
        Completed(stdout="ericson-j-santos\n"),
        Completed(returncode=1),
    ])
    monkeypatch.setattr(probe.shutil, "which", lambda name: "gh.exe")
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs: next(calls))
    result = probe.github_runner_registry_probe()
    assert result == {
        "ok": False,
        "state": "runner_registry_access_denied",
        "http_hint": "forbidden_or_missing_permission",
    }


def test_runtime_migration_e2e_is_branch_scoped_exact_sha_and_sanitized() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "ops/noteri-runtime-migration-e2e-20260923" in workflow
    assert "ericson-j-santos/noteri-runtime" in workflow
    assert "07e6108974e87c0f5f71587e4ad4ab0cdf05188c" in workflow
    assert "noteri_runtime_isolated_e2e.py" in workflow
    assert "Validate independent evidence contract" in workflow
    assert "idempotency_missing" in workflow
    assert "negative_control_missing" in workflow
    assert "rdc_dependency_detected" in workflow
    assert "secrets." not in workflow
