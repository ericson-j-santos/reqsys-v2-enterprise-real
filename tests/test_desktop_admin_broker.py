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
    ):
        (scripts / name).write_text("# stub\n", encoding="utf-8")
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


def test_register_task_contract_requires_s4u_highest() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "TASK_LOGON_S4U = 2" in source
    assert "TASK_RUNLEVEL_HIGHEST = 1" in source
    assert 'definition.Principal' in source
    assert 'principal.LogonType = TASK_LOGON_S4U' in source
    assert 'principal.RunLevel = TASK_RUNLEVEL_HIGHEST' in source
