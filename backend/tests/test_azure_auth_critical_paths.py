"""Testes de caminhos críticos — validação Azure AD."""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from jwt.exceptions import PyJWKClientConnectionError

from app.services import azure_auth as auth


@pytest.fixture(autouse=True)
def _circuit_breaker_isolado():
    auth.reset_circuit_breaker()
    yield
    auth.reset_circuit_breaker()


def test_extrair_usuario_usa_preferred_username():
    usuario = auth.extrair_usuario({'preferred_username': 'ops@example.com', 'name': 'Operador'})

    assert usuario['email'] == 'ops@example.com'
    assert usuario['nome'] == 'Operador'


def test_extrair_usuario_fallback_email():
    usuario = auth.extrair_usuario({'email': 'dev@example.com'})

    assert usuario['email'] == 'dev@example.com'
    assert usuario['nome']


@patch('app.services.azure_auth._get_jwks_client')
def test_validar_token_azure_rejeita_jwks_invalido(mock_jwks):
    mock_jwks.return_value.get_signing_key_from_jwt.side_effect = RuntimeError('jwks offline')

    with pytest.raises(ValueError, match='Token inválido'):
        auth.validar_token_azure('token', 'tenant', 'client')


@patch('app.services.azure_auth.jwt.decode')
@patch('app.services.azure_auth._get_jwks_client')
def test_validar_token_azure_aceita_issuer_v2(mock_jwks, mock_decode):
    key = MagicMock()
    key.key = 'public'
    mock_jwks.return_value.get_signing_key_from_jwt.return_value = key
    mock_decode.side_effect = [
        jwt.exceptions.InvalidIssuerError('mismatch'),
        {'sub': 'user-1', 'preferred_username': 'user@example.com'},
    ]

    claims = auth.validar_token_azure('token', 'tenant-id', 'client-id')

    assert claims['sub'] == 'user-1'
    assert mock_decode.call_count == 2


@patch('app.services.azure_auth.jwt.decode')
@patch('app.services.azure_auth._get_jwks_client')
def test_validar_token_azure_falha_quando_issuers_invalidos(mock_jwks, mock_decode):
    key = MagicMock()
    key.key = 'public'
    mock_jwks.return_value.get_signing_key_from_jwt.return_value = key
    mock_decode.side_effect = jwt.exceptions.InvalidIssuerError('mismatch')

    with pytest.raises(ValueError, match='issuer não reconhecido'):
        auth.validar_token_azure('token', 'tenant-id', 'client-id')


@patch('app.services.azure_auth.jwt.decode')
@patch('app.services.azure_auth._get_jwks_client')
def test_validar_token_azure_tenta_novamente_apos_falha_transitoria_jwks(mock_jwks, mock_decode):
    chamadas = {'n': 0}
    sonos = []
    key = MagicMock()
    key.key = 'public'

    def fake_get_signing_key(_id_token):
        chamadas['n'] += 1
        if chamadas['n'] < 3:
            raise PyJWKClientConnectionError('jwks indisponivel')
        return key

    mock_jwks.return_value.get_signing_key_from_jwt.side_effect = fake_get_signing_key
    mock_decode.return_value = {'sub': 'user-1', 'preferred_username': 'user@example.com'}

    claims = auth.validar_token_azure('token', 'tenant-id', 'client-id', sleep=sonos.append)

    assert claims['sub'] == 'user-1'
    assert chamadas['n'] == 3
    assert len(sonos) == 2


@patch('app.services.azure_auth._get_jwks_client')
def test_validar_token_azure_circuito_abre_apos_falhas_consecutivas(mock_jwks):
    mock_jwks.return_value.get_signing_key_from_jwt.side_effect = PyJWKClientConnectionError('azure ad fora do ar')

    for _ in range(3):
        with pytest.raises(ValueError, match='Token inválido'):
            auth.validar_token_azure('token', 'tenant-id', 'client-id', sleep=lambda _s: None, max_retries=1)

    with pytest.raises(ValueError, match="Circuito 'azure_jwks' aberto"):
        auth.validar_token_azure('token', 'tenant-id', 'client-id', sleep=lambda _s: None)
