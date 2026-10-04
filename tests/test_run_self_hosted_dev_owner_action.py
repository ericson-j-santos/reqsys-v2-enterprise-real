"""Security contracts for the two closed DEV owner action phases."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/run_self_hosted_dev_owner_action.py"
SPEC = importlib.util.spec_from_file_location("closed_owner_action", FILE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
SOURCE_SHA = "a" * 40
SCRIPT_SHA = "b" * 64

@pytest.mark.parametrize("phase", ("restore", "activate", "shell", "prod"))
def test_phase_is_closed(phase):
    with pytest.raises(SystemExit):
        m.build_parser().parse_args([
            phase, "--source-sha", SOURCE_SHA, "--script-sha256", SCRIPT_SHA
        ])

@pytest.mark.parametrize("extra", ("--source-root", "--command", "--url", "--timeout"))
def test_no_arbitrary_route_inputs(extra):
    with pytest.raises(SystemExit):
        m.build_parser().parse_args([
            "recipient", "--source-sha", SOURCE_SHA, "--script-sha256", SCRIPT_SHA,
            extra, "arbitrary",
        ])

def test_two_exact_child_commands():
    root = Path("C:/dev/chatgpt-workers") / ("rs2-" + SOURCE_SHA)
    python = "C:/owned/python.exe"
    assert m.child_command("recipient", root, SOURCE_SHA, python) == [
        python, str(root / "scripts/dev_backup_transport.py"), "recipient-init",
        "--confirm", "INIT-PC24X7-DEV-MIGRATION-IDENTITY",
    ]
    assert m.child_command("prepare", root, SOURCE_SHA, python) == [
        python, str(root / "scripts/reqsys_self_hosted_dev_publish.py"), "prepare",
        "--source-root", str(root), "--expected-sha", SOURCE_SHA,
        "--correlation-id", "pc24x7-owner-dev-" + SOURCE_SHA[:12],
    ]
    with pytest.raises(m.OperationError):
        m.child_command("activate", root, SOURCE_SHA, python)

@pytest.mark.parametrize("failure", (
    "source_origin_mismatch", "source_head_mismatch", "source_tree_dirty",
    "script_not_tracked", "script_sha256_mismatch", "reparse_path_blocked",
))
def test_binding_failure_never_executes(monkeypatch, failure):
    calls = []
    def denied(*_):
        raise m.OperationError(failure)
    monkeypatch.setattr(m, "validate_execution", denied)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    with pytest.raises(m.OperationError, match=failure):
        m.execute("recipient", SOURCE_SHA, SCRIPT_SHA)
    assert not calls

@pytest.mark.parametrize("phase,timeout", (("recipient", 120), ("prepare", 840)))
def test_child_is_bounded_and_output_is_suppressed(monkeypatch, tmp_path, phase, timeout):
    calls = []
    monkeypatch.setattr(m, "validate_execution", lambda *_: tmp_path)
    monkeypatch.setattr(m, "python_executable", lambda: "C:/owned/python.exe")
    monkeypatch.setattr(m, "validate_active_grant", lambda *_: None)
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"PRIVATE-DATA", stderr=b"PRIVATE-DATA")
    monkeypatch.setattr(m.subprocess, "run", run)
    evidence = m.execute(phase, SOURCE_SHA, SCRIPT_SHA)
    assert len(calls) == 1
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == timeout <= 900
    assert calls[0][1]["cwd"] == str(tmp_path)
    assert "PRIVATE-DATA" not in str(evidence)
    assert evidence["usable"] is False
    assert evidence["dev_pointer_changed"] is False

def repository_answers(root):
    return {
        ("rev-parse", "--show-toplevel"): str(root.resolve()),
        ("remote", "get-url", "origin"): m.REMOTE,
        ("rev-parse", "HEAD"): SOURCE_SHA,
        ("status", "--porcelain", "--untracked-files=all"): "",
        ("ls-files", "-v"): "H scripts/normal.py",
    }

@pytest.mark.parametrize("command,bad,code", (
    (("remote", "get-url", "origin"), "https://github.com/other/repo.git", "source_origin_mismatch"),
    (("rev-parse", "HEAD"), "c" * 40, "source_head_mismatch"),
    (("status", "--porcelain", "--untracked-files=all"), " M tracked.py", "source_tree_dirty"),
    (("ls-files", "-v"), "h assumed.py", "source_index_flags_untrusted"),
    (("ls-files", "-v"), "S skipped.py", "source_index_flags_untrusted"),
))
def test_actual_repository_guards(monkeypatch, tmp_path, command, bad, code):
    answers = repository_answers(tmp_path)
    answers[command] = bad
    monkeypatch.setattr(m, "git_read", lambda _root, args: answers[tuple(args)])
    with pytest.raises(m.OperationError, match=code):
        m.validate_repository(tmp_path, SOURCE_SHA)

def test_git_read_has_no_optional_writes_or_global_auth(monkeypatch, tmp_path):
    observed = {}
    monkeypatch.setenv("GIT_SSH_COMMAND", "untrusted-command")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    def run(command, **kwargs):
        observed.update(kwargs)
        assert command[:3] == ["git", "-c", "core.longpaths=true"]
        return SimpleNamespace(returncode=0, stdout=SOURCE_SHA + "\n", stderr="")
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.git_read(tmp_path, ["rev-parse", "HEAD"]) == SOURCE_SHA
    assert observed["shell"] is False
    assert observed["env"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert observed["env"]["GIT_CONFIG_GLOBAL"] == m.os.devnull
    assert observed["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert "GIT_SSH_COMMAND" not in observed["env"]
    assert "GIT_CONFIG_COUNT" not in observed["env"]

def test_script_digest_and_tracking_are_both_required(monkeypatch, tmp_path):
    path = tmp_path / m.SCRIPTS["recipient"]
    path.parent.mkdir()
    path.write_bytes(b"fixed-script")
    monkeypatch.setattr(m, "git_read", lambda _root, args: args[-1])
    with pytest.raises(m.OperationError, match="script_sha256_mismatch"):
        m.validate_scripts(tmp_path, {m.SCRIPTS["recipient"]: "0" * 64})
    monkeypatch.setattr(m, "git_read", lambda *_: "other.py")
    with pytest.raises(m.OperationError, match="script_not_tracked"):
        m.validate_scripts(tmp_path, {m.SCRIPTS["recipient"]: SCRIPT_SHA})

def test_launcher_cannot_run_outside_fixed_source(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "require_host", lambda: None)
    monkeypatch.setattr(m, "source_root", lambda _: tmp_path)
    with pytest.raises(m.OperationError, match="launcher_location_mismatch"):
        m.validate_execution("recipient", SOURCE_SHA, SCRIPT_SHA)


def test_no_active_grant_means_no_child_execution(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(m, "validate_execution", lambda *_: tmp_path)
    monkeypatch.setattr(m, "python_executable", lambda: "C:/owned/python.exe")
    def denied(*_):
        raise m.OperationError("active_private_grant_required")
    monkeypatch.setattr(m, "validate_active_grant", denied)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    with pytest.raises(m.OperationError, match="active_private_grant_required"):
        m.execute("recipient", SOURCE_SHA, SCRIPT_SHA)
    assert not calls


FINGERPRINT = "PRIVATE-OWNER-TEST"
LAUNCHER_DIGEST = "c" * 64
GRANT_NOW = datetime(2026, 10, 3, 13, 17, tzinfo=timezone.utc)

def active_payload(phase="recipient"):
    root = m.source_root(SOURCE_SHA)
    python = "C:/owned/python.exe"
    return {
        "version": 1, "enabled": True, "owner_fingerprint": FINGERPRINT,
        "development_mode": {"enabled": False},
        "actions": {m.ACTION_IDS[phase]: {
            "environment": "dev", "scope": m.SCOPES[phase],
            "valid_from": "2026-10-03T13:00:00+00:00",
            "expires_at": "2026-10-03T14:00:00+00:00",
            "command": [
                python, str(root / m.LAUNCHER), phase,
                "--source-sha", SOURCE_SHA, "--script-sha256", SCRIPT_SHA,
            ],
            "grant_contract": m.GRANT_CONTRACT, "source_sha": SOURCE_SHA,
            "script_sha256": SCRIPT_SHA, "launcher_sha256": LAUNCHER_DIGEST,
        }},
    }

def validate_payload(payload, now=GRANT_NOW, fingerprint=FINGERPRINT, phase="recipient"):
    m.validate_grant_payload(
        payload, phase, SOURCE_SHA, SCRIPT_SHA, LAUNCHER_DIGEST,
        "C:/owned/python.exe", now, fingerprint,
    )

@pytest.mark.parametrize("phase", ("recipient", "prepare"))
def test_active_payload_matches_exact_closed_command(phase):
    validate_payload(active_payload(phase), phase=phase)

@pytest.mark.parametrize("change", (
    "command", "scope", "digest", "launcher", "source", "extra", "environment", "marker",
))
def test_grant_payload_tampering_is_rejected(change):
    payload = active_payload()
    grant = payload["actions"][m.ACTION_IDS["recipient"]]
    if change == "command":
        grant["command"] = ["python", "arbitrary.py"]
    elif change == "scope":
        grant["scope"] = m.SCOPES["prepare"]
    elif change == "digest":
        grant["script_sha256"] = "d" * 64
    elif change == "launcher":
        grant["launcher_sha256"] = "d" * 64
    elif change == "source":
        grant["source_sha"] = "d" * 40
    elif change == "extra":
        grant["unknown"] = True
    elif change == "environment":
        grant["environment"] = "prod"
    else:
        grant["grant_contract"] = "other"
    with pytest.raises(m.OperationError, match="private_grant_binding_mismatch"):
        validate_payload(payload)

@pytest.mark.parametrize("now", (
    datetime(2026, 10, 3, 12, 59, tzinfo=timezone.utc),
    datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc),
))
def test_future_or_expired_grant_is_blocked(now):
    with pytest.raises(m.OperationError, match="private_grant_expired_or_window_invalid"):
        validate_payload(active_payload(), now=now)

def test_grant_owner_and_disabled_mode_are_enforced():
    with pytest.raises(m.OperationError, match="private_grant_owner_or_enabled_mismatch"):
        validate_payload(active_payload(), fingerprint="DIFFERENT-OWNER")
    payload = active_payload()
    payload["development_mode"]["enabled"] = True
    with pytest.raises(m.OperationError, match="broad_development_mode_must_remain_disabled"):
        validate_payload(payload)
