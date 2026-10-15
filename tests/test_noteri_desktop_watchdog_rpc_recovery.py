_then_requeried_and_started(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    query_count = 0
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal query_count
        calls.append(argv)
        if "/Query" in argv:
            query_count += 1
            return (
                completed(1, stderr="ERRO: O sistema nÃ£o pode encontrar o arquivo especificado.")
                if query_count == 1
                else completed(0, TASK_XML)
            )
        return completed(0, "SUCCESS")

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        repair=lambda: {
            "headless_boot_ready": True,
            "registration_method": "schtasks_np",
            "activation_pending": False,
        },
        source_host="DESKTOP-PDQK954",
        platform="nt",
    )
    assert result["ok"] is True
    assert result["initial_query_returncode"] == 1
    assert result["task_repair_attempted"] is True
    assert result["task_repair_verified"] is True
    assert result["task_created_or_modified"] is True
    assert query_count == 2
    assert any("/Run" in call for call in calls)


def test_invalid_task_configuration_is_not_started(tmp_path: Path, monkeypatch) -> None:
    bad_xml = TASK_XML.replace("<LogonType>S4U</LogonType>", "<LogonType>InteractiveToken</LogonType>")
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return completed(0, bad_xml)

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        source_host="DESKTOP-PDQK954",
        platform="nt",
    )
    assert result["result"] == "DESKTOP_WATCHDOG_CONFIGURATION_NOT_READY"
    assert len(calls) == 1


def test_disabled_task_is_not_started(tmp_path: Path, monkeypatch) -> None:
    disabled_xml = TASK_XML.replace(
        "</Principals>",
        "</Principals><Settings><Enabled>false</Enabled></Settings>",
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return completed(0, disabled_xml)

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        source_host="DESKTOP-PDQK954",
        platform="nt",
    )
    assert result["result"] == "DESKTOP_WATCHDOG_CONFIGURATION_NOT_READY"
    assert len(calls) == 1


def test_wrong_source_host_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(m.RecoveryError, match="host_origem_nao_autorizado"):
        m.recover(
            confirm=m.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            source_host="Noteri",
            platform="nt",
        )


def test_workflow_modes_are_bounded_governed_and_read_only() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    # Superfície única e explicitamente limitada: nenhum input livre além do modo.
    assert "workflow_dispatch:" in raw
    assert "mode:" in raw
    assert "type: choice" in raw
    assert "default: watchdog" in raw
    for mode in ("watchdog", "watchdog-uac", "watchdog-uac-stage", "runner-recover", "runner-bootstrap", "runner-canary", "alm-runner-bootstrap", "reboot-once", "dedicated-readonly", "dedicated-recover"):
        assert f"- {mode}" in raw
    assert raw.count("description: 'Bounded recovery mode'") == 1

    # Permissões e invariantes comuns permanecem somente leitura/fail-closed.
    assert "contents: read" in raw
    assert "contents: write" not in raw
    assert "actions: write" not in raw
    assert "secrets." not in raw
    assert "persist-credentials: false" in raw
    assert "chatgpt-operational-rules" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "state_validated" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "2"' in raw
    assert '"--expected-head", $env:ANCHOR_SHA' in raw
    assert "TARGET_REPO: ${{ github.workspace }}" in raw
    assert "path: _target" not in raw
    assert "C:\\dev\\reqsys-v2-enterprise-real" not in raw
    assert "shell: pwsh" not in raw
    assert "actions/checkout@v4" not in raw
    assert "actions/upload-artifact@v4" not in raw
    assert raw.count("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1") == 15
    assert "actions/setup-python@" not in raw
    assert "Get-Command python" not in raw
    assert raw.count("Prepare pinned portable Python 3.12") == 7
    assert raw.count("python-3.12.10-embed-amd64.zip") == 7
    assert raw.count("4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3") == 7
    assert raw.count("[Security.Cryptography.SHA256]::Create()") == 7
    assert "Get-FileHash" not in raw
    assert raw.count("REQSYS_PYTHON=$python") == 7
    assert raw.count("python312._pth") == 7
    assert raw.count("$rulesScripts = Join-Path $env:GITHUB_WORKSPACE") == 7
    assert raw.count("PORTABLE_PYTHON_PTH_MISSING") == 7
    assert raw.count("--require-runner-version-preflight") == 6
    assert raw.count("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a") == 8

    # Modo watchdog executa localmente no Desktop e permanece restrito à tarefa fixa existente.
    assert "inputs.mode == 'watchdog-uac'" in raw
    assert "RUN-EXISTING-DESKTOP-WATCHDOG" in raw
    assert "DESKTOP_WATCHDOG_RECOVERY_NOT_CONFIRMED" in raw
    assert "$recoveryScript = Join-Path $env:TARGET_PATH" in raw
    assert "noteri_desktop_watchdog_rpc_recovery.py" in raw
    recover = raw.split("  recover:", 1)[1].split("  reboot-once:", 1)[0]
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in recover
    assert "TARGET_REPO: C:\\dev\\chatgpt-workers\\reqsys-watchdog-session-source" in recover
    assert "Prepare dedicated clean session source" in recover
    assert "SESSION_SOURCE_REMOTE_HEAD_MISMATCH" in recover
    assert "git clone --no-checkout --local $env:GITHUB_WORKSPACE $source" in recover
    assert 'if ($e.source_host -ne "DESKTOP-PDQK954")' in recover
    assert 'if ($e.execution_mode -ne "local_pc24x7_runner")' in recover
    assert 'if ($e.remote_access_attempted)' in recover
    assert "Materialize verified persistent watchdog Python" in recover
    assert '"--source-sha", $env:ANCHOR_SHA' in recover
    assert '"--allow-uac"' in recover
    assert '"--uac-confirm", "LAUNCH-DESKTOP-CONTROL-PLANE-WATCHDOG-UAC"' in recover
    assert "UNVERIFIED_TASK_MUTATION_REPORTED" in recover
    stage = raw.split("  stage-watchdog-uac:", 1)[1].split("  recover:", 1)[0]
    assert "DESKTOP_WATCHDOG_UAC_LAUNCHER_STAGED" in stage
    assert "Ativar-ReqSys-Watchdog.cmd" in stage
    assert 'GetFolderPath("CommonDesktopDirectory")' in stage
    assert "desktop_paths = @($staged" in stage
    assert "powershell_paths = @($staged" in stage
    assert "repair_paths = @($staged" in stage
    assert "native_repair_diagnostic = $nativeDiagnostic" in stage
    assert "NATIVE_DIAGNOSTIC_INVALID" in stage
    assert "if ($diagnosticError.Length -gt 500)" in stage
    assert "ReqSys-Watchdog-Reparador-Nativo.ps1" in stage
    assert "repair_source_sha = $env:GITHUB_SHA.ToLowerInvariant()" in stage
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in stage
    assert "public_desktop_staged" in stage
    assert "stage_failures = $stageFailures" in stage
    assert "RUNNER_PROFILE_DESKTOP_LAUNCHER_NOT_STAGED" in stage
    assert "repair_desktop_watchdog_native.ps1" in stage
    assert "repair_desktop_control_plane_native.ps1" not in stage
    assert 'execution_method = "native_powershell_watchdog_task_scheduler_com"' in stage
    assert "-Verb RunAs -Wait -PassThru" in stage
    assert "DESKTOP_WATCHDOG_NATIVE_REPAIRED" in stage
    assert 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Ativar-ReqSys-Watchdog.ps1"' in stage
    assert "requires_local_uac_approval = $true" in stage
    assert "remote_uac_attempted = $false" in stage
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in stage

    # Reboot one-shot usa a exceção canônica separada e consumível, somente no Noteri.
    assert "reboot-once:" in raw
    assert "if: ${{ inputs.mode == 'reboot-once' }}" in raw
    assert "owner_remote_host_power_once.py" in raw
    assert "REMOTE_REBOOT_REPLAY_WAS_NOT_BLOCKED" in raw
    assert "authorization_revoked = $true" in raw

    # Recovery direto reutiliza o contrato permanente já instalado, sem bootstrap.
    assert "runner-recover:" in raw
    assert "if: ${{ inputs.mode == 'runner-recover' }}" in raw
    assert "noteri_desktop_orchestrator_runner_recovery.py" in raw
    assert "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR" in raw
    assert "DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED" in raw
    assert "host.github_runner.recover.v1" in raw

    # Bootstrap usa somente o Noteri e o action id fixo já allowlisted no Orchestrator.
    assert "runner-bootstrap:" in raw
    assert "if: ${{ inputs.mode == 'runner-bootstrap' }}" in raw
    assert "Bootstrap registered Desktop GitHub runner through control plane" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    runner_bootstrap = raw.split("  runner-bootstrap:", 1)[1].split(
        "  runner-canary:", 1
    )[0]
    assert "timeout-minutes: 12" in runner_bootstrap
    assert '"--timeout", "150"' in runner_bootstrap
    assert '"--timeout-seconds", "90"' in runner_bootstrap
    assert "desktop_runner_bootstrap_via_orchestrator.py" in raw
    assert "BOOTSTRAP-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR" in raw
    assert "DESKTOP_GITHUB_RUNNER_LOCAL_BOOTSTRAP_VERIFIED" in raw
    assert "IDEMPOTENCY_NOT_PROVEN" in raw

    # Canário terminal exige pickup no runner físico exato, não apenas listener local.
    assert "runner-canary:" in raw
    assert "if: ${{ inputs.mode == 'runner-canary' }}" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "desktop_runner_pickup_canary.py" in raw
    assert "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP" in raw
    assert "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN" in raw
    assert "DESKTOP-PDQK954" in raw

    # Todos os modos físicos não ligados à exceção de reboot usam a main canônica atual.
    assert raw.count("562fc4274aff24f7058cb135f27a509aa69031c1") == 4
    runner_canary = raw.split("  runner-canary:", 1)[1].split("  alm-runner-bootstrap:", 1)[0]
    assert "RULES_SHA: f6ccb143a581e28650e9b640226f9ef671d469f2" in runner_canary
    assert "RULES_SHA: 562fc4274aff24f7058cb135f27a509aa69031c1" not in runner_canary
    assert "881d9ca2f8e77025edb7298b22981109c567a730" not in raw
    assert "5af7b5ab6e31c24744176abd774855168c55953f" not in raw

    # Dedicated listener extension is isolated, fixed-identity, and manually gated.
    assert "- dedicated-readonly" in raw
    assert "- dedicated-recover" in raw
    assert "dedicated_recovery_confirm:" in raw
    dedicated = raw.split("  dedicated-listener:", 1)[1]
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in dedicated
    assert "TARGET_REPO: C:\\dev\\chatgpt-workers\\reqsys-watchdog-session-source" in dedicated
    assert "desktop_dedicated_listener_recovery.py" in dedicated
    assert "ericson-j-santos/desktop-pc24x7-runtime" in dedicated
    assert "DESKTOP-PDQK954-runtime" in dedicated
    assert "DESKTOP_DEDICATED_LISTENER_READONLY_OK" in dedicated
    assert 'GITHUB_TOKEN: ${{ github.token }}' in dedicated
    assert '"--risk", "2"' in dedicated
    assert "activate_desktop_runtime_runner.py" not in raw
