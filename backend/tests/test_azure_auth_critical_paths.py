"""Testes de caminhos críticos — validação Azure AD."""

from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.services import azure_auth as auth


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
