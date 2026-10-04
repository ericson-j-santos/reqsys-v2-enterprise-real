from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.identity_governance import IdentityGovernanceError
from app.services import teams_graph_identity as identity_service


def _write_registry(tmp_path, *, environment='test', purpose='teams-proactive-messaging', classification='confidential', rotated_at=None, secret_ref='env://TEAMS_GRAPH_TEST_SECRET'):
    rotated = rotated_at or datetime.now(timezone.utc)
    payload = [
        {
            'name': 'reqsys-test-teams-confidential',
            'environment': environment,
            'purpose': purpose,
            'data_classification': classification,
            'tenant_id': 'tenant-governado',
            'client_id': 'client-governado-12345678',
            'current_secret_ref': secret_ref,
            'next_secret_ref': 'env://TEAMS_GRAPH_TEST_SECRET_NEXT',
            'rotated_at': rotated.isoformat(),
            'max_age_days': 60,
        }
    ]
    path = tmp_path / 'identity-governance.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def _configure(monkeypatch, tmp_path, **kwargs):
    path = _write_registry(tmp_path, **kwargs)
    monkeypatch.setenv('REQSYS_IDENTITY_GOVERNANCE_FILE', str(path))
    monkeypatch.setenv('TEAMS_GRAPH_TEST_SECRET', 'secret-governado')
    monkeypatch.setenv('TEAMS_GRAPH_TEST_SECRET_NEXT', 'next-secret')
    monkeypatch.setattr(identity_service.settings, 'app_environment', 'test')
    return path


def test_resolve_identidade_usa_perfil_teams_confidential(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    identity = identity_service.resolve_teams_graph_identity()

    assert identity.tenant_id == 'tenant-governado'
    assert identity.client_id == 'client-governado-12345678'
    assert identity.client_secret == 'secret-governado'
    assert identity.evidence()['data_classification'] == 'confidential'
    assert 'client_secret' not in identity.evidence()


def test_resolve_identidade_bloqueia_finalidade_incorreta(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, purpose='interactive-login')

    with pytest.raises(IdentityGovernanceError, match='Identidade não resolvida'):
        identity_service.resolve_teams_graph_identity()


def test_resolve_identidade_bloqueia_credencial_vencida(monkeypatch, tmp_path):
    _configure(
        monkeypatch,
        tmp_path,
        rotated_at=datetime.now(timezone.utc) - timedelta(days=90),
    )

    with pytest.raises(IdentityGovernanceError, match='expirou'):
        identity_service.resolve_teams_graph_identity()


def test_resolve_identidade_bloqueia_segredo_ausente(monkeypatch, tmp_path):
    path = _write_registry(tmp_path, secret_ref='env://TEAMS_GRAPH_SECRET_AUSENTE')
    monkeypatch.setenv('REQSYS_IDENTITY_GOVERNANCE_FILE', str(path))
    monkeypatch.delenv('TEAMS_GRAPH_SECRET_AUSENTE', raising=False)
    monkeypatch.setattr(identity_service.settings, 'app_environment', 'test')

    with pytest.raises(IdentityGovernanceError, match='não resolvido'):
        identity_service.resolve_teams_graph_identity()


def test_keyvault_sem_provider_bloqueia(monkeypatch, tmp_path):
    path = _write_registry(tmp_path, secret_ref='keyvault://reqsys/teams/current')
    monkeypatch.setenv('REQSYS_IDENTITY_GOVERNANCE_FILE', str(path))
    monkeypatch.setattr(identity_service.settings, 'app_environment', 'test')

    with pytest.raises(IdentityGovernanceError, match='keyvault'):
        identity_service.resolve_teams_graph_identity()


def test_referencia_sem_provider_bloqueia():
    with pytest.raises(IdentityGovernanceError, match='Referência de segredo inválida'):
        identity_service._resolve_secret_reference('TEAMS_GRAPH_SECRET')


def test_referencia_sem_chave_bloqueia():
    with pytest.raises(IdentityGovernanceError, match='sem chave'):
        identity_service._resolve_secret_reference('env://')


def test_provider_desconhecido_bloqueia():
    with pytest.raises(IdentityGovernanceError, match='não suportado'):
        identity_service._resolve_secret_reference('arquivo://segredo')


def test_vault_local_resolve_sem_fallback_remoto():
    with (
        patch('app.services.teams_graph_identity.read_secret_from_vault', return_value='vault-secret') as local,
        patch('app.services.teams_graph_identity.read_secret_from_remote_vault') as remoto,
    ):
        secret = identity_service._resolve_secret_reference('vault://reqsys/teams/current')

    assert secret == 'vault-secret'
    local.assert_called_once_with('reqsys/teams/current')
    remoto.assert_not_called()


def test_vault_remoto_e_usado_quando_local_vazio():
    with (
        patch('app.services.teams_graph_identity.read_secret_from_vault', return_value=None),
        patch('app.services.teams_graph_identity.read_secret_from_remote_vault', return_value='remote-secret') as remoto,
    ):
        secret = identity_service._resolve_secret_reference('vault://reqsys/teams/current')

    assert secret == 'remote-secret'
    remoto.assert_called_once_with('reqsys/teams/current')


def test_status_identidade_configurada(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    status = identity_service.teams_graph_identity_status()

    assert status['configured'] is True
    assert status['profile_name'] == 'reqsys-test-teams-confidential'
    assert status['data_classification'] == 'confidential'
    assert 'client_secret' not in status


def test_status_identidade_invalida_retorna_bloqueio(monkeypatch):
    monkeypatch.delenv('REQSYS_IDENTITY_GOVERNANCE_FILE', raising=False)

    status = identity_service.teams_graph_identity_status()

    assert status['configured'] is False
    assert 'IDENTITY_GOVERNANCE_FILE' in status['error']


@patch('app.services.teams_graph_identity.httpx.AsyncClient')
def test_token_usa_tenant_client_e_secret_do_registro(mock_client_cls, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {'access_token': 'token-governado'}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = client

    token, identity = asyncio.run(identity_service.acquire_teams_graph_token())

    assert token == 'token-governado'
    assert identity.profile_name == 'reqsys-test-teams-confidential'
    args, kwargs = client.post.call_args
    assert args[0].endswith('/tenant-governado/oauth2/v2.0/token')
    assert kwargs['data']['client_id'] == 'client-governado-12345678'
    assert kwargs['data']['client_secret'] == 'secret-governado'
    assert kwargs['data']['scope'] == 'https://graph.microsoft.com/.default'


@patch('app.services.teams_graph_identity.httpx.AsyncClient')
def test_token_sem_access_token_bloqueia(mock_client_cls, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = client

    with pytest.raises(IdentityGovernanceError, match='não retornou access_token'):
        asyncio.run(identity_service.acquire_teams_graph_token())
