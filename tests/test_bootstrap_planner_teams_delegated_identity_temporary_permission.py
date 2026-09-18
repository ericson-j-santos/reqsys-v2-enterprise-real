from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/bootstrap_planner_teams_delegated_identity_temporary_permission.py")
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_planner_teams_delegated_identity_temporary_permission",
    SCRIPT,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _args(*, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        confirm=MODULE.CONFIRMATION,
        tenant_id="tenant-dev",
        mutator_client_id="mutator-client",
        repository=MODULE.DEFAULT_REPOSITORY,
        environment=MODULE.DEFAULT_ENVIRONMENT,
        credential_name=MODULE.DEFAULT_CREDENTIAL_NAME,
        vault_name=MODULE.DEFAULT_VAULT,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
        dry_run=dry_run,
    )


def _ctx() -> object:
    return MODULE.Context("tenant-dev", "mutator-app", "mutator-sp", "graph-sp")


def test_non_owner_fails_without_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_resolve_context", lambda *_: _ctx())
    monkeypatch.setattr(MODULE, "_owners", lambda *_: [])
    called = {"grant": False}
    monkeypatch.setattr(MODULE, "_grant_ownedby", lambda *_: called.__setitem__("grant", True))

    result = MODULE.execute(_args())

    assert result["status"] == "blocked"
    assert result["reason"] == "MUTATOR_NOT_OWNER"
    assert result["application_readwrite_all_granted"] is False
    assert called["grant"] is False


def test_dry_run_does_not_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_resolve_context", lambda *_: _ctx())
    monkeypatch.setattr(MODULE, "_owners", lambda *_: ["mutator-sp"])
    monkeypatch.setattr(MODULE, "_existing_ownedby_assignment", lambda *_: None)
    called = {"grant": False}
    monkeypatch.setattr(MODULE, "_grant_ownedby", lambda *_: called.__setitem__("grant", True))

    result = MODULE.execute(_args(dry_run=True))

    assert result["status"] == "dry_run"
    assert called["grant"] is False


def test_happy_path_revokes_ownedby_in_finally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_resolve_context", lambda *_: _ctx())
    monkeypatch.setattr(MODULE, "_owners", lambda *_: ["mutator-sp"])
    states = iter([None, {"id": "temp"}, None])
    monkeypatch.setattr(MODULE, "_existing_ownedby_assignment", lambda *_: next(states))
    monkeypatch.setattr(MODULE, "_grant_ownedby", lambda *_: "temp")
    monkeypatch.setattr(MODULE, "_main_sha", lambda *_: "abc")
    monkeypatch.setattr(
        MODULE,
        "_dispatch_bootstrap_workflow",
        lambda *_: {"run_id": 123, "head_sha": "abc", "conclusion": "success"},
    )
    monkeypatch.setattr(MODULE, "_verify_acceptance_fic", lambda *_: True)
    monkeypatch.setattr(MODULE, "_dedicated_client_id", lambda *_: "client-dedicated")
    monkeypatch.setattr(MODULE, "_verify_dedicated_app", lambda *_: True)
    revoked: list[str] = []
    monkeypatch.setattr(MODULE, "_revoke_assignment", lambda _sp, assignment: revoked.append(assignment))

    result = MODULE.execute(_args())

    assert result["status"] == "ready"
    assert result["ownedby_temporarily_granted"] is True
    assert result["ownedby_revoked"] is True
    assert result["application_readwrite_all_granted"] is False
    assert result["admin_consent_granted"] is False
    assert result["client_secret_created"] is False
    assert revoked == ["temp"]


def test_workflow_failure_still_revokes_ownedby(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_resolve_context", lambda *_: _ctx())
    monkeypatch.setattr(MODULE, "_owners", lambda *_: ["mutator-sp"])
    states = iter([None, {"id": "temp"}])
    monkeypatch.setattr(MODULE, "_existing_ownedby_assignment", lambda *_: next(states))
    monkeypatch.setattr(MODULE, "_grant_ownedby", lambda *_: "temp")
    monkeypatch.setattr(MODULE, "_main_sha", lambda *_: "abc")
    monkeypatch.setattr(
        MODULE,
        "_dispatch_bootstrap_workflow",
        lambda *_: (_ for _ in ()).throw(MODULE.BootstrapError("workflow_failed")),
    )
    revoked: list[str] = []
    monkeypatch.setattr(MODULE, "_revoke_assignment", lambda _sp, assignment: revoked.append(assignment))

    with pytest.raises(MODULE.BootstrapError, match="workflow_failed"):
        MODULE.execute(_args())

    assert revoked == ["temp"]


def test_preexisting_ownedby_is_not_revoked_implicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_resolve_context", lambda *_: _ctx())
    monkeypatch.setattr(MODULE, "_owners", lambda *_: ["mutator-sp"])
    monkeypatch.setattr(MODULE, "_existing_ownedby_assignment", lambda *_: {"id": "existing"})
    revoked: list[str] = []
    monkeypatch.setattr(MODULE, "_revoke_assignment", lambda *_: revoked.append("unexpected"))

    result = MODULE.execute(_args())

    assert result["status"] == "blocked"
    assert result["reason"] == "OWNEDBY_ALREADY_PRESENT"
    assert revoked == []
