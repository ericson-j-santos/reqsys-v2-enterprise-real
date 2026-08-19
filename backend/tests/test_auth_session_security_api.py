from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import auth


def _snapshot(epoch: int = 7):
    return SimpleNamespace(
        session_epoch=epoch,
        authz_version='rbac-test-current',
        invalidated_at=None,
        invalidated_by=None,
        invalidation_reason=None,
        correlation_id='corr-status-test',
    )


def test_current_session_recalcula_permissoes_vigentes(monkeypatch):
    monkeypatch.setattr(auth, 'snapshot', lambda: _snapshot())

    response = auth.current_session({'papel': 'admin', 'auth_provider': 'azure'})
    data = response['data']

    assert data['papel'] == 'admin'
    assert 'teams-recipient-policies:admin' in data['permissoes']
    assert 'security-sessions:admin' in data['permissoes']
    assert data['session_epoch'] == 7
    assert data['authz_version'] == 'rbac-test-current'
    assert data['auth_provider'] == 'azure'


def test_refresh_session_emite_token_com_permissoes_atualizadas(monkeypatch):
    emitido = {}

    def fake_criar_token(payload):
        emitido.update(payload)
        return 'token-atualizado'

    monkeypatch.setattr(auth, 'criar_token', fake_criar_token)
    monkeypatch.setattr(auth, 'snapshot', lambda: _snapshot(epoch=8))

    response = auth.refresh_session(
        {'sub': 'admin@example.com', 'papel': 'admin', 'auth_provider': 'certificate'}
    )
    data = response['data']

    assert emitido == {
        'sub': 'admin@example.com',
        'papel': 'admin',
        'auth_provider': 'certificate',
    }
    assert data['access_token'] == 'token-atualizado'
    assert data['usuario']['session_epoch'] == 8
    assert 'teams-recipient-policies:admin' in data['usuario']['permissoes']


def test_sessions_admin_status_retorna_estado_sanitizado(monkeypatch):
    monkeypatch.setattr(auth, 'snapshot', lambda: _snapshot(epoch=3))
    monkeypatch.setattr(auth, '_session_confirmation_phrase', lambda: 'INVALIDAR-SESSOES-DEV')

    response = auth.sessions_admin_status({'papel': 'admin'})
    data = response['data']

    assert data['session_epoch'] == 3
    assert data['authz_version'] == 'rbac-test-current'
    assert data['required_confirmation'] == 'INVALIDAR-SESSOES-DEV'
    assert data['active_session_inventory'] == 'stateless_not_enumerated'
    assert 'token' not in data
    assert 'secret' not in data


def test_invalidate_all_rejeita_confirmacao_incorreta(monkeypatch):
    monkeypatch.setattr(auth, '_session_confirmation_phrase', lambda: 'INVALIDAR-SESSOES-DEV')
    body = auth.InvalidateAllSessionsInput(
        confirmacao='CONFIRMACAO-INVALIDA',
        motivo='Alteração controlada de RBAC',
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.sessions_admin_invalidate_all(body, {'sub': 'admin@example.com'}, object())

    assert exc_info.value.status_code == 409


def test_invalidate_all_incrementa_epoch_e_registra_auditoria(monkeypatch):
    state = _snapshot(epoch=9)
    chamadas = {}

    def fake_invalidate_all(*, actor, reason, correlation_id, db):
        chamadas['invalidate'] = {
            'actor': actor,
            'reason': reason,
            'correlation_id': correlation_id,
            'db': db,
        }
        return state

    def fake_registrar_evento(*args):
        chamadas['audit'] = args

    db = object()
    monkeypatch.setattr(auth, '_session_confirmation_phrase', lambda: 'INVALIDAR-SESSOES-DEV')
    monkeypatch.setattr(auth, 'obter_correlation_id', lambda: 'corr-invalidate-test')
    monkeypatch.setattr(auth, 'invalidate_all', fake_invalidate_all)
    monkeypatch.setattr(auth, 'registrar_evento', fake_registrar_evento)
    monkeypatch.setattr(auth, 'snapshot', lambda: state)

    body = auth.InvalidateAllSessionsInput(
        confirmacao='INVALIDAR-SESSOES-DEV',
        motivo='Alteração controlada de RBAC',
    )
    response = auth.sessions_admin_invalidate_all(body, {'sub': 'admin@example.com'}, db)
    data = response['data']

    assert chamadas['invalidate']['reason'] == 'Alteração controlada de RBAC'
    assert chamadas['invalidate']['correlation_id'] == 'corr-invalidate-test'
    assert chamadas['invalidate']['db'] is db
    assert chamadas['audit'][3] == 'INVALIDAR_TODAS_SESSOES'
    assert data['session_epoch'] == 9
    assert data['decision'] == 'all_human_sessions_invalidated'


def test_masked_actor_preserva_identificador_tecnico_sem_email():
    assert auth._masked_actor('admin-runtime') == 'admin-runtime'
