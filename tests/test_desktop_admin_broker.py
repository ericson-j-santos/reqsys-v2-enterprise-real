from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "desktop_admin_broker.py"
SPEC = importlib.util.spec_from_file_location("desktop_admin_broker", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def gh_comment(
    *,
    comment_id: int = 100,
    body: str = "/reqsys admin desktop status",
    actor: str = "ericson-j-santos",
    association: str = "OWNER",
    created: datetime | None = None,
    edited: bool = False,
) -> dict:
    created = created or datetime.now(timezone.utc)
    updated = created + timedelta(seconds=1) if edited else created
    return {
        "id": comment_id,
        "body": body,
        "user": {"login": actor},
        "author_association": association,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": updated.isoformat().replace("+00:00", "Z"),
    }


def test_rejects_other_host(monkeypatch) -> None:
    monkeypatch.setattr(m.os, "name", "nt")
    monkeypatch.setattr(m.socket, "gethostname", lambda: "Noteri")
    with pytest.raises(m.BrokerError, match="host não autorizado"):
        m.require_windows_desktop()


def test_allowlist_is_exact_and_has_no_shell_action() -> None:
    assert set(m.ALLOWED_COMMANDS) == {
        "/reqsys admin desktop status",
        "/reqsys admin desktop recover-control-plane",
        "/reqsys admin desktop recover-rdc",
        "/reqsys admin desktop recover-runner",
        "/reqsys admin desktop activate-watchdog",
        "/reqsys run pc24x7-runner-pool-onboard",
    }
    source = MODULE.read_text(encoding="utf-8").casefold()
    assert "shell=true" not in source
    assert "host.shell" not in source
    assert "reboot" not in " ".join(m.ALLOWED_COMMANDS).casefold()


def test_transport_is_outbound_public_github_only_without_secret_or_listener() -> None:
    source = MODULE.read_text(encoding="utf-8")
    lowered = source.casefold()
    assert "api.github.com/repos/{repository}/issues/{issue_number}/comments" in lowered
    assert "authorization" not in lowered
    assert "gh_token" not in lowered
    assert "github_token" not in lowered
    assert "threadinghttpserver" not in lowered
    assert "http.server" not in lowered
    assert ".listen(" not in lowered
    assert ".bind(" not in lowered


def test_comment_authorization_requires_owner_exact_unedited_fresh() -> None:
    now = datetime.now(timezone.utc)
    not_before = now - timedelta(seconds=30)
    assert m.authorize_comment(gh_comment(created=now), not_before=not_before, reference_time=now) == "status"
    assert m.authorize_comment(gh_comment(actor="other", created=now), not_before=not_before, reference_time=now) is None
    assert m.authorize_comment(gh_comment(association="MEMBER", created=now), not_before=not_before, reference_time=now) is None
    assert m.authorize_comment(gh_comment(body="/reqsys admin desktop shell", created=now), not_before=not_before, reference_time=now) is None
    assert m.authorize_comment(gh_comment(created=now, edited=True), not_before=not_before, reference_time=now) is None
    assert m.authorize_comment(
        gh_comment(created=now - timedelta(seconds=m.MAX_COMMENT_AGE_SECONDS + 1)),
        not_before=now - timedelta(hours=1),
        reference_time=now,
    ) is None


def test_comment_before_activation_is_rejected() -> None:
    now = datetime.now(timezone.utc)
    comment = gh_comment(created=now - timedelta(seconds=5))
    assert m.authorize_comment(
        comment,
        not_before=now,
        reference_time=now,
    ) is None


def test_process_once_is_idempotent_by_comment_id(monkeypatch, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    metadata = {
        "runtime_root": str(tmp_path),
        "not_before": (now - timedelta(seconds=30)).isoformat(),
    }
    comment = gh_comment(comment_id=101, created=now)
    monkeypatch.setattr(m, "fetch_comments", lambda since: [comment, comment])
    calls = []
    monkeypatch.setattr(
        m,
        "execute_action",
        lambda action, meta, comment_id: calls.append((action, comment_id)) or {"ok": True},
    )
    first = m.process_once(metadata, reference_time=now)
    second = m.process_once(metadata, reference_time=now)
    assert first["commands_accepted"] == 1
    assert second["commands_accepted"] == 0
    assert calls == [("status", 101)]


def test_failed_command_is_recorded_and_not_replayed(monkeypatch, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    metadata = {
        "runtime_root": str(tmp_path),
        "not_before": (now - timedelta(seconds=30)).isoformat(),
    }
    comment = gh_comment(comment_id=102, body="/reqsys admin desktop recover-rdc", created=now)
    monkeypatch.setattr(m, "fetch_comments", lambda since: [comment])
    monkeypatch.setattr(m, "execute_action", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("known failure")))
    first = m.process_once(metadata, reference_time=now)
    second = m.process_once(metadata, reference_time=now)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert first["commands_accepted"] == 1
    assert second["commands_accepted"] == 0
    assert state["accepted"]["status"] == "failed"
    assert state["accepted"]["comment_id"] == 102


def test_install_stages_release_and_marks_uac_pending(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for name in (
        "desktop_admin_broker.py",
        "desktop_admin_broker_uac_launcher.py",
        m.WATCHDOG_SCRIPT,
        m.WATCHDOG_UAC_SCRIPT,
        m.RDC_RECOVERY_SCRIPT,
        m.RUNNER_BOOTSTRAP_SCRIPT,
        m.RUNNER_INSTALL_SCRIPT,
        m.RUNNER_ONBOARD_SCRIPT,
        m.RUNNER_PREFLIGHT_SCRIPT,
    ):
        (scripts / name).write_text("# stub\n", encoding="utf-8")
    config = source / "config"
    config.mkdir()
    (config / m.RUNNER_POOL_POLICY).write_text("{}\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "require_windows_desktop", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(
        m,
        "register_task",
        lambda **kwargs: (_ for _ in ()).throw(m.BrokerError("task_scheduler_access_denied")),
    )
    result = m.install(
        source,
        source_sha="a" * 40,
        python_executable=python,
        runtime_root=runtime,
        poll_seconds=90,
        confirm=m.INSTALL_CONFIRM,
    )
    assert result["ok"] is True
    assert result["activation_pending"] is True
    assert result["requires_uac_activation"] is True
    metadata = json.loads((runtime / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["activation_pending"] is True
    assert (runtime / "releases" / ("a" * 40) / "scripts" / "desktop_admin_broker.py").is_file()
    assert (runtime / "releases" / ("a" * 40) / "scripts" / "desktop_admin_broker_uac_launcher.py").is_file()
    activation = runtime / "Activate-Desktop-Admin-Broker.cmd"
    assert activation.is_file()
    activation_text = activation.read_text(encoding="utf-8")
    assert "LAUNCH-DESKTOP-ADMIN-BROKER-UAC" in activation_text
    assert "--metadata" in activation_text
    assert "--command" not in activation_text
    assert "--action" not in activation_text


def test_register_task_from_metadata_records_sanitized_evidence(monkeypatch, tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    metadata.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(m, "now_iso", lambda: "2026-10-24T23:00:00+00:00")
    monkeypatch.setattr(
        m,
        "register_task_from_metadata",
        lambda path: {"ok": True, "task_name": m.TASK_NAME},
    )

    result = m.register_task_from_metadata_with_evidence(metadata)

    evidence = json.loads((tmp_path / m.ACTIVATION_EVIDENCE_FILE).read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert evidence["ok"] is True
    assert evidence["result"] == "DESKTOP_ADMIN_BROKER_TASK_REGISTERED"
    assert evidence["production_touched"] is False
    assert evidence["secrets_read"] is False


def test_register_task_from_metadata_records_failure_without_secret(monkeypatch, tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    metadata.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(m, "now_iso", lambda: "2026-10-24T23:00:00+00:00")
    monkeypatch.setattr(
        m,
        "register_task_from_metadata",
        lambda path: (_ for _ in ()).throw(m.BrokerError("task_registration_failed")),
    )

    with pytest.raises(m.BrokerError, match="task_registration_failed"):
        m.register_task_from_metadata_with_evidence(metadata)

    evidence = json.loads((tmp_path / m.ACTIVATION_EVIDENCE_FILE).read_text(encoding="utf-8"))
    assert evidence["ok"] is False
    assert evidence["result"] == "DESKTOP_ADMIN_BROKER_ACTIVATION_BLOCKED"
    assert evidence["error_code"] == "activation_unexpected_error"
    assert evidence["production_touched"] is False
    assert evidence["secrets_read"] is False


def test_recover_runner_uses_fixed_noninteractive_bootstrap(monkeypatch, tmp_path: Path) -> None:
    release = tmp_path / "release"
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    (scripts / m.RUNNER_BOOTSTRAP_SCRIPT).write_text("# stub\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append([str(item) for item in argv])
        payload = {
            "ok": True,
            "state": "runtime_active",
            "runner_running": True,
            "runner_registry_present": True,
            "runner_registry_status": "online",
            "runner_registry_labels_ok": True,
            "runner_registered_now": True,
            "runner_started_now": True,
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload) + "\n", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    result = m._recover_runner(
        {
            "release_root": str(release),
            "source_sha": "a" * 40,
        }
    )

    assert result["bootstrap_state"] == "runtime_active"
    assert result["runner_registry_status"] == "online"
    assert len(calls) == 1
    argv = calls[0]
    assert "--non-interactive-auth" in argv
    assert argv[argv.index("--repo-root") + 1] == str(release)
    assert argv[argv.index("--source-sha") + 1] == "a" * 40


def test_recover_runner_fails_closed_on_bootstrap_error(monkeypatch, tmp_path: Path) -> None:
    release = tmp_path / "release"
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    (scripts / m.RUNNER_BOOTSTRAP_SCRIPT).write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(
        m.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            4,
            stdout='{"ok": false, "state": "github_auth_required"}\n',
            stderr="",
        ),
    )
    with pytest.raises(m.BrokerError, match="runner_bootstrap_failed:github_auth_required"):
        m._recover_runner(
            {
                "release_root": str(release),
                "source_sha": "b" * 40,
            }
        )


def test_runner_onboard_action_requires_elevated_broker(monkeypatch) -> None:
    monkeypatch.setattr(m, "_is_admin", lambda: False)
    with pytest.raises(m.BrokerError, match="elevated_broker_required"):
        m._onboard_runner_base({})


def test_runner_onboard_action_is_fixed_dev_base_without_labels(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    scripts = source / "scripts"
    config = source / "config"
    runner = tmp_path / "runner"
    scripts.mkdir(parents=True)
    config.mkdir()
    runner.mkdir()
    for name in (m.RUNNER_INSTALL_SCRIPT, m.RUNNER_PREFLIGHT_SCRIPT):
        (scripts / name).write_text("# stub\n", encoding="utf-8")
    (config / m.RUNNER_POOL_POLICY).write_text("{}\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    comment = gh_comment(
        comment_id=501,
        body=m.RUNNER_ONBOARD_COMMAND,
        created=now,
    )
    calls: list[list[str]] = []
    restarts: list[str] = []

    def fake_run(argv, **kwargs):
        calls.append([str(item) for item in argv])
        return subprocess.CompletedProcess(argv, 0, stdout='{"status":"eligible"}\n', stderr="")

    monkeypatch.setattr(m, "_is_admin", lambda: True)
    monkeypatch.setattr(m, "fetch_comment_by_id", lambda comment_id: comment)
    monkeypatch.setattr(m, "_validate_checkout", lambda path, sha: source)
    monkeypatch.setattr(m, "_validate_runner_root", lambda path: runner)
    monkeypatch.setattr(m, "_runner_service_name", lambda path: "actions.runner.owner.repo.pc24x7")
    monkeypatch.setattr(m, "_schedule_runner_restart", lambda service: restarts.append(service))
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    monkeypatch.setenv("SystemDrive", str(tmp_path / "system"))
    monkeypatch.setenv("ProgramData", str(tmp_path / "programdata"))
    monkeypatch.setenv("SystemRoot", str(tmp_path / "windows"))

    result = m._onboard_runner_base(
        {
            "not_before": (now - timedelta(seconds=1)).isoformat(),
            "runner_onboard_request": {
                "owner_comment_id": 501,
                "source_sha": "a" * 40,
                "source_root": str(source),
                "runner_root": str(runner),
            },
        }
    )

    assert result["profile"] == "base"
    assert result["environment"] == "dev"
    assert result["admin_route"] == "scheduled_task_s4u_highest"
    assert result["admin_secret_supplied"] is False
    assert result["labels_applied"] is False
    assert result["production_touched"] is False
    assert restarts == ["actions.runner.owner.repo.pc24x7"]
    assert len(calls) == 2
    installer = calls[0]
    assert installer[installer.index("-Profile") + 1] == "base"
    assert "-ApplyGitHubLabels" not in installer
    assert "-RestartRunnerService" not in installer
    assert "--profile" in calls[1]
    assert calls[1][calls[1].index("--profile") + 1] == "base"


def test_runner_onboard_stage_requires_existing_s4u_highest_task(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(m, "require_windows_desktop", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(
        m,
        "task_status",
        lambda: {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "InteractiveToken",
            "run_level": "highest",
            "enabled": True,
        },
    )
    with pytest.raises(m.BrokerError, match="admin_broker_task_contract_invalid"):
        m.stage_runner_onboard(
            tmp_path,
            source_sha="a" * 40,
            runner_root=tmp_path,
            owner_comment_id=501,
            confirm=m.RUNNER_ONBOARD_STAGE_CONFIRM,
        )


def test_register_task_contract_requires_s4u_highest() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "TASK_LOGON_S4U = 2" in source
    assert "TASK_RUNLEVEL_HIGHEST = 1" in source
    assert 'definition.Principal' in source
    assert 'principal.LogonType = TASK_LOGON_S4U' in source
    assert 'principal.RunLevel = TASK_RUNLEVEL_HIGHEST' in source
