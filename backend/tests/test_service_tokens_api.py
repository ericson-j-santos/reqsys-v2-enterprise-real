"""Testes de integração para os endpoints REST de service tokens (app/api/service_tokens.py)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.auditoria import AuditoriaEvento
from app.models.service_token import ServiceToken

client = TestClient(app)
ADMIN_EMAIL = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
ANALISTA_EMAIL = 'analista@tieri659.onmicrosoft.com'


def _token(email: str) -> str:
    resp = client.post('/v1/auth/login', json={'email': email})
    return resp.json()['data']['access_token']


def _admin_headers() -> dict[str, str]:
    return {'Authorization': f'Bearer {_token(ADMIN_EMAIL)}'}


class TestCriarServiceToken:
    def test_sem_jwt_retorna_401(self):
        resp = client.post('/v1/admin/service-tokens', json={'label': 'x', 'scopes': ['a:b']})
        assert resp.status_code == 401

    def test_analista_bloqueado_403(self):
        headers = {'Authorization': f'Bearer {_token(ANALISTA_EMAIL)}'}
        resp = client.post('/v1/admin/service-tokens', json={'label': 'x', 'scopes': ['a:b']}, headers=headers)
        assert resp.status_code == 403

    def test_admin_cria_com_sucesso_e_token_so_aparece_uma_vez(self):
        resp = client.post(
            '/v1/admin/service-tokens',
            json={'label': 'ci-teams-import', 'scopes': ['teams_gateway:promover_solution']},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['label'] == 'ci-teams-import'
        assert data['scopes'] == ['teams_gateway:promover_solution']
        assert isinstance(data['token'], str) and len(data['token']) > 20
        assert data['expira_em'] is None

        db = SessionLocal()
        try:
            registro = db.query(ServiceToken).filter(ServiceToken.id == data['id']).one()
            assert registro.token_hash != data['token']  # nunca grava em claro
            evento = (
                db.query(AuditoriaEvento)
                .filter(AuditoriaEvento.acao == 'SERVICE_TOKEN_CRIADO', AuditoriaEvento.entidade_id == str(data['id']))
                .first()
            )
            assert evento is not None
        finally:
            db.close()

    def test_scopes_vazio_retorna_422(self):
        resp = client.post('/v1/admin/service-tokens', json={'label': 'x', 'scopes': []}, headers=_admin_headers())
        assert resp.status_code == 422

    def test_expires_in_days_negativo_retorna_422(self):
        resp = client.post(
            '/v1/admin/service-tokens',
            json={'label': 'x', 'scopes': ['a:b'], 'expires_in_days': -1},
            headers=_admin_headers(),
        )
        assert resp.status_code == 422

    def test_expires_in_days_positivo_grava_expiracao(self):
        resp = client.post(
            '/v1/admin/service-tokens',
            json={'label': 'x-com-prazo', 'scopes': ['a:b'], 'expires_in_days': 30},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()['data']['expira_em'] is not None


class TestListarServiceTokens:
    def test_lista_nao_expoe_valor_do_token(self):
        criar = client.post(
            '/v1/admin/service-tokens', json={'label': 'ci-listar', 'scopes': ['*']}, headers=_admin_headers()
        )
        assert criar.status_code == 200

        resp = client.get('/v1/admin/service-tokens', headers=_admin_headers())
        assert resp.status_code == 200
        tokens = resp.json()['data']['tokens']
        assert any(t['label'] == 'ci-listar' for t in tokens)
        for t in tokens:
            assert 'token' not in t
            assert 'token_hash' not in t


class TestRevogarServiceToken:
    def test_revogar_idempotente(self):
        criar = client.post(
            '/v1/admin/service-tokens', json={'label': 'ci-revogar-2', 'scopes': ['a:b']}, headers=_admin_headers()
        )
        token_id = criar.json()['data']['id']

        primeira = client.delete(f'/v1/admin/service-tokens/{token_id}', headers=_admin_headers())
        segunda = client.delete(f'/v1/admin/service-tokens/{token_id}', headers=_admin_headers())

        assert primeira.status_code == 200
        assert segunda.status_code == 200
        assert primeira.json()['data']['revogado'] is True
        assert segunda.json()['data']['revogado'] is True

    def test_revogar_inexistente_404(self):
        resp = client.delete('/v1/admin/service-tokens/999999999', headers=_admin_headers())
        assert resp.status_code == 404
