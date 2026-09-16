from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py')
SPEC = importlib.util.spec_from_file_location('bootstrap_pc24x7_teams_oidc_temporary_permission', SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        confirm=MODULE.CONFIRMATION,
        tenant_id='tenant-dev',
        mutator_client_id='mutator-client-id',
        repository=MODULE.DEFAULT_REPOSITORY,
        environment=MODULE.DEFAULT_ENVIRONMENT,
        credential_name=MODULE.DEFAULT_CREDENTIAL_NAME,
        dry_run=False,
    )


def test_non_owner_bloqueia_sem_conceder_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_resolve_context', lambda *_: MODULE.Context('tenant-dev', 'app', 'sp', 'graph'))
    monkeypatch.setattr(MODULE, '_owners', lambda *_: [])
    called = {'grant': False}
    monkeypatch.setattr(MODULE, '_grant_ownedby', lambda *_: called.__setitem__('grant', True))
    result = MODULE.execute(_args())
    assert result['status'] == 'blocked'
    assert result['reason'] == 'MUTATOR_NOT_OWNER'
    assert result['application_readwrite_all_granted'] is False
    assert called['grant'] is False


def test_preexisting_ownedby_nao_e_revogado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_resolve_context', lambda *_: MODULE.Context('tenant-dev', 'app', 'sp', 'graph'))
    monkeypatch.setattr(MODULE, '_owners', lambda *_: ['sp'])
    monkeypatch.setattr(MODULE, '_existing_ownedby_assignment', lambda *_: {'id': 'existing'})
    result = MODULE.execute(_args())
    assert result['status'] == 'blocked'
    assert result['reason'] == 'OWNEDBY_ALREADY_PRESENT'


def test_happy_path_revoga_em_finally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_resolve_context', lambda *_: MODULE.Context('tenant-dev', 'app', 'sp', 'graph'))
    monkeypatch.setattr(MODULE, '_owners', lambda *_: ['sp'])
    states = iter([None, {'id': 'temp'}, None])
    monkeypatch.setattr(MODULE, '_existing_ownedby_assignment', lambda *_: next(states))
    monkeypatch.setattr(MODULE, '_grant_ownedby', lambda *_: 'temp')
    monkeypatch.setattr(MODULE, '_dispatch_bootstrap_workflow', lambda *_: {'run_id': 123, 'head_sha': 'abc', 'conclusion': 'success'})
    monkeypatch.setattr(MODULE, '_verify_fic', lambda *_: True)
    revoked: list[str] = []
    monkeypatch.setattr(MODULE, '_revoke_assignment', lambda _sp, assignment: revoked.append(assignment))
    result = MODULE.execute(_args())
    assert result['status'] == 'ready'
    assert result['ownedby_temporarily_granted'] is True
    assert result['ownedby_revoked'] is True
    assert result['application_readwrite_all_granted'] is False
    assert revoked == ['temp']


def test_falha_no_workflow_ainda_revoga(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_resolve_context', lambda *_: MODULE.Context('tenant-dev', 'app', 'sp', 'graph'))
    monkeypatch.setattr(MODULE, '_owners', lambda *_: ['sp'])
    states = iter([None, {'id': 'temp'}])
    monkeypatch.setattr(MODULE, '_existing_ownedby_assignment', lambda *_: next(states))
    monkeypatch.setattr(MODULE, '_grant_ownedby', lambda *_: 'temp')
    monkeypatch.setattr(MODULE, '_dispatch_bootstrap_workflow', lambda *_: (_ for _ in ()).throw(MODULE.BootstrapError('workflow failed')))
    revoked: list[str] = []
    monkeypatch.setattr(MODULE, '_revoke_assignment', lambda _sp, assignment: revoked.append(assignment))
    with pytest.raises(MODULE.BootstrapError, match='workflow failed'):
        MODULE.execute(_args())
    assert revoked == ['temp']
