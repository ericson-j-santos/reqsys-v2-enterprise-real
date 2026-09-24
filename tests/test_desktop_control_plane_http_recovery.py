from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "backend" / "app" / "services" / "desktop_control_plane_recovery.py"
API = ROOT / "backend" / "app" / "api" / "desktop_control_plane_recovery.py"
MAIN = ROOT / "backend" / "app" / "main.py"

SPEC = importlib.util.spec_from_file_location("desktop_control_plane_recovery", SERVICE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def _comment(comment_id: int, now: datetime, *, body: str | None = None) -> dict:
    timestamp = now.isoformat().replace("+00:00", "Z")
    return {
        "id": comment_id,
        "body": body or m.COMMAND,
        "user": {"login": m.EXPECTED_ACTOR},
        "author_association": m.EXPECTED_ASSOCIATION,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_contract_is_fixed_and_has_no_shell_surface() -> None:
    source = SERVICE.read_text(encoding="utf-8").casefold()
    assert m.REPOSITORY == "ericson-j-santos/desktop-pc24x7-runtime"
    assert m.ISSUE_NUMBER == 2
    assert m.COMMAND == "/desktop-runtime admin recover-control-plane"
    assert m.DEV_ENVIRONMENTS == {"development", "dev", "desenvolvimento"}
    assert "subprocess" not in source
    assert "shell=true" not in source
    assert "powershell" not in source
    assert "cmd.exe" not in source
    assert "eval(" not in source


def test_reuses_fresh_exact_owner_command(monkeypatch) -> None:
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)
    monkeypatch.setattr(m, "settings", SimpleNamespace(normalized_environment="development"))
    calls: list[tuple[str, str, dict | None]] = []

    def transport(method: str, url: str, token: str, payload):
        calls.append((method, url, payload))
        assert token == "token"
        if method == "GET":
            return 200, [_comment(1234, now - timedelta(seconds=30))]
        raise AssertionError("POST não deve ocorrer quando há comando fresco")

    result = m.dispatch_control_plane_recovery(
        "corr-http-recovery-001",
        transport=transport,
        now=now,
        token="token",
    )
    assert result["accepted"] is True
    assert result["broker_comment_id"] == 1234
    assert result["reused_fresh_command"] is True
    assert result["arbitrary_command_supported"] is False
    assert [item[0] for item in calls] == ["GET"]


def test_creates_only_exact_allowlisted_command_when_needed(monkeypatch) -> None:
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)
    monkeypatch.setattr(m, "settings", SimpleNamespace(normalized_environment="dev"))
    calls: list[tuple[str, str, dict | None]] = []

    def transport(method: str, url: str, token: str, payload):
        calls.append((method, url, payload))
        if method == "GET":
            return 200, []
        assert method == "POST"
        assert payload == {"body": m.COMMAND}
        return 201, {"id": 5678}

    result = m.dispatch_control_plane_recovery(
        "corr-http-recovery-002",
        transport=transport,
        now=now,
        token="token",
    )
    assert result["broker_comment_id"] == 5678
    assert result["broker_correlation_id"] == "desktop-admin-gh-comment-5678"
    assert result["reused_fresh_command"] is False
    assert result["transport"] == "reqsys_dev_http_8083_to_desktop_runtime_broker"
    assert result["remote_shell_used"] is False
    assert result["production_touched"] is False
    assert [item[0] for item in calls] == ["GET", "POST"]


def test_rejects_non_dev_before_transport(monkeypatch) -> None:
    monkeypatch.setattr(m, "settings", SimpleNamespace(normalized_environment="production"))
    with pytest.raises(m.DesktopRecoveryDispatchError, match="environment_not_allowed"):
        m.dispatch_control_plane_recovery(
            "corr-http-recovery-003",
            transport=lambda *args: pytest.fail("transporte não deve ser chamado"),
            token="token",
        )


def test_rejects_invalid_or_edited_comment_for_reuse(monkeypatch) -> None:
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)
    monkeypatch.setattr(m, "settings", SimpleNamespace(normalized_environment="development"))
    edited = _comment(999, now - timedelta(seconds=10))
    edited["updated_at"] = now.isoformat().replace("+00:00", "Z")
    calls: list[str] = []

    def transport(method: str, url: str, token: str, payload):
        calls.append(method)
        if method == "GET":
            return 200, [edited]
        return 201, {"id": 1000}

    result = m.dispatch_control_plane_recovery(
        "corr-http-recovery-004",
        transport=transport,
        now=now,
        token="token",
    )
    assert result["broker_comment_id"] == 1000
    assert calls == ["GET", "POST"]


def test_api_is_admin_only_fixed_endpoint_and_main_wiring() -> None:
    api = API.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert 'prefix="/api/internal/desktop-control-plane"' in api
    assert '@router.post("/recover"' in api
    assert "Depends(require_admin)" in api
    assert "DesktopControlPlaneRecoveryInput" in api
    assert "action" not in DesktopControlPlaneRecoveryInput_fields(api)
    assert "app.include_router(desktop_control_plane_recovery.router)" in main


def DesktopControlPlaneRecoveryInput_fields(source: str) -> set[str]:
    block = source.split("class DesktopControlPlaneRecoveryInput", 1)[1].split("@router.post", 1)[0]
    fields = set()
    for line in block.splitlines():
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith(("class ", "#")):
            fields.add(stripped.split(":", 1)[0])
    return fields
