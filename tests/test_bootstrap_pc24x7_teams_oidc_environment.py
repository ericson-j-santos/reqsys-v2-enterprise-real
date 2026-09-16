from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path('scripts/bootstrap_pc24x7_teams_oidc_environment.py')
SPEC = importlib.util.spec_from_file_location('bootstrap_pc24x7_teams_oidc_environment', SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _args(*, dry_run: bool = False, tenant_id: str = 'tenant-dev') -> argparse.Namespace:
    return argparse.Namespace(
        confirm=MODULE.CONFIRMATION,
        tenant_id=tenant_id,
        mutator_client_id='mutator-client-id',
        repository=MODULE.DEFAULT_REPOSITORY,
        environment=MODULE.DEFAULT_ENVIRONMENT,
        credential_name=MODULE.DEFAULT_CREDENTIAL_NAME,
        dry_run=dry_run,
    )


def _exact() -> dict:
    return {
        'name': MODULE.DEFAULT_CREDENTIAL_NAME,
        'issuer': MODULE.ISSUER,
        'subject': MODULE._expected_subject(MODULE.DEFAULT_REPOSITORY, MODULE.DEFAULT_ENVIRONMENT),
        'audiences': [MODULE.AUDIENCE],
    }


def test_subject_e_exatamente_o_environment_development() -> None:
    assert MODULE._expected_subject(MODULE.DEFAULT_REPOSITORY, MODULE.DEFAULT_ENVIRONMENT) == (
        'repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development'
    )


def test_dry_run_nao_cria_fic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_account_tenant', lambda: 'tenant-dev')
    monkeypatch.setattr(MODULE, '_app_object_id', lambda _: 'object-id')
    monkeypatch.setattr(MODULE, '_list_credentials', lambda _: [])

    result = MODULE.bootstrap(_args(dry_run=True))

    assert result['status'] == 'dry_run'
    assert result['planned_action'] == 'create_federated_identity_credential'
    assert result['rbac_changed'] is False
    assert result['secret_value_exposed'] is False


def test_fic_existente_e_idempotente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_account_tenant', lambda: 'tenant-dev')
    monkeypatch.setattr(MODULE, '_app_object_id', lambda _: 'object-id')
    monkeypatch.setattr(MODULE, '_list_credentials', lambda _: [_exact()])

    result = MODULE.bootstrap(_args())

    assert result['status'] == 'ready'
    assert result['created'] is False
    assert result['rbac_changed'] is False


def test_nome_igual_com_contrato_diferente_falha_fechado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_account_tenant', lambda: 'tenant-dev')
    monkeypatch.setattr(MODULE, '_app_object_id', lambda _: 'object-id')
    bad = _exact()
    bad['subject'] = 'repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:other'
    monkeypatch.setattr(MODULE, '_list_credentials', lambda _: [bad])

    with pytest.raises(MODULE.BootstrapError, match='contrato diferente'):
        MODULE.bootstrap(_args())


def test_tenant_incorreto_bloqueia_antes_de_consultar_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_account_tenant', lambda: 'tenant-outro')

    called = False

    def app_lookup(_: str) -> str:
        nonlocal called
        called = True
        return 'object-id'

    monkeypatch.setattr(MODULE, '_app_object_id', app_lookup)

    with pytest.raises(MODULE.BootstrapError, match='Tenant Azure ativo difere'):
        MODULE.bootstrap(_args())

    assert called is False


def test_criacao_real_rele_e_comprova_contrato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, '_account_tenant', lambda: 'tenant-dev')
    monkeypatch.setattr(MODULE, '_app_object_id', lambda _: 'object-id')

    reads = iter([[], [_exact()]])
    monkeypatch.setattr(MODULE, '_list_credentials', lambda _: next(reads))

    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ''
        stderr = ''

    def fake_run(args: list[str], *, check: bool = True):
        calls.append(args)
        return Result()

    monkeypatch.setattr(MODULE, '_run', fake_run)

    result = MODULE.bootstrap(_args())

    assert result['status'] == 'ready'
    assert result['created'] is True
    assert result['rbac_changed'] is False
    assert len(calls) == 1
    command = calls[0]
    assert command[:4] == ['az', 'rest', '--method', 'POST']
    body = command[command.index('--body') + 1]
    assert 'environment:development' in body
    assert 'api://AzureADTokenExchange' in body
    assert 'Application.ReadWrite' not in body
