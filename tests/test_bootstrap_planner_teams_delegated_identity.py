from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/bootstrap_planner_teams_delegated_identity.py")
SPEC = importlib.util.spec_from_file_location("bootstrap_planner_teams_delegated_identity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _args(*, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        confirm=MODULE.CONFIRMATION,
        tenant_id="tenant-dev",
        app_display_name=MODULE.DEFAULT_APP_NAME,
        vault_name=MODULE.DEFAULT_VAULT,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
        dry_run=dry_run,
        output="ignored.json",
    )


def _app() -> dict:
    return {
        "id": "object-1",
        "appId": "client-1",
        "displayName": MODULE.DEFAULT_APP_NAME,
    }


def _details() -> dict:
    return {
        "id": "object-1",
        "appId": "client-1",
        "displayName": MODULE.DEFAULT_APP_NAME,
        "signInAudience": MODULE.EXPECTED_AUDIENCE,
        "isFallbackPublicClient": True,
        "requiredResourceAccess": [],
    }


def test_invalid_confirmation_fails_closed() -> None:
    args = _args()
    args.confirm = "NOPE"
    with pytest.raises(MODULE.BootstrapError, match="confirmacao_invalida"):
        MODULE.bootstrap(args)


def test_dry_run_has_no_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_tenant", lambda: "tenant-dev")
    monkeypatch.setattr(MODULE, "_assert_vault", lambda _vault: None)
    monkeypatch.setattr(MODULE, "_find_app", lambda _name: None)
    called = {"create": False}
    monkeypatch.setattr(MODULE, "_create_app", lambda _name: called.__setitem__("create", True))

    result = MODULE.bootstrap(_args(dry_run=True))

    assert result["status"] == "dry_run"
    assert result["client_secret_created"] is False
    assert result["admin_consent_granted"] is False
    assert called["create"] is False


def test_existing_app_is_reused_without_secret_or_admin_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_tenant", lambda: "tenant-dev")
    monkeypatch.setattr(MODULE, "_assert_vault", lambda _vault: None)
    monkeypatch.setattr(MODULE, "_find_app", lambda _name: _app())
    monkeypatch.setattr(MODULE, "_app_details", lambda _app_id: _details())
    monkeypatch.setattr(MODULE, "_ensure_public_client", lambda *_: False)
    monkeypatch.setattr(MODULE, "_ensure_permissions", lambda *_: True)
    monkeypatch.setattr(MODULE, "_ensure_service_principal", lambda _app_id: False)
    stored: list[tuple[str, str, str]] = []
    monkeypatch.setattr(MODULE, "_store_client_id", lambda v, n, a: stored.append((v, n, a)))
    monkeypatch.setattr(MODULE, "_delete_app", lambda _object_id: pytest.fail("must not delete reused app"))

    result = MODULE.bootstrap(_args())

    assert result["status"] == "ready"
    assert result["created_app"] is False
    assert result["permissions_changed"] is True
    assert result["client_secret_created"] is False
    assert result["admin_consent_granted"] is False
    assert stored == [(MODULE.DEFAULT_VAULT, MODULE.DEFAULT_CLIENT_ID_SECRET, "client-1")]


def test_created_app_rolls_back_when_keyvault_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_tenant", lambda: "tenant-dev")
    monkeypatch.setattr(MODULE, "_assert_vault", lambda _vault: None)
    monkeypatch.setattr(MODULE, "_find_app", lambda _name: None)
    monkeypatch.setattr(MODULE, "_create_app", lambda _name: _app())
    monkeypatch.setattr(MODULE, "_app_details", lambda _app_id: _details())
    monkeypatch.setattr(MODULE, "_ensure_public_client", lambda *_: False)
    monkeypatch.setattr(MODULE, "_ensure_permissions", lambda *_: False)
    monkeypatch.setattr(MODULE, "_ensure_service_principal", lambda _app_id: True)
    monkeypatch.setattr(
        MODULE,
        "_store_client_id",
        lambda *_: (_ for _ in ()).throw(MODULE.BootstrapError("keyvault_failed")),
    )
    deleted: list[str] = []
    monkeypatch.setattr(MODULE, "_delete_app", lambda object_id: deleted.append(object_id))

    with pytest.raises(MODULE.BootstrapError, match="keyvault_failed"):
        MODULE.bootstrap(_args())

    assert deleted == ["object-1"]


def test_merge_required_access_preserves_existing_and_adds_scopes() -> None:
    current = [{
        "resourceAppId": "resource-a",
        "resourceAccess": [{"id": "existing-role", "type": "Role"}],
    }]
    resources = [
        {"appId": "resource-a", "scopes": {"Read": "scope-read"}},
        {"appId": "resource-b", "scopes": {"Manage": "scope-manage"}},
    ]

    merged, changed = MODULE._merge_required_access(current, resources)

    assert changed is True
    by_id = {item["resourceAppId"]: item["resourceAccess"] for item in merged}
    assert {"id": "existing-role", "type": "Role"} in by_id["resource-a"]
    assert {"id": "scope-read", "type": "Scope"} in by_id["resource-a"]
    assert {"id": "scope-manage", "type": "Scope"} in by_id["resource-b"]
