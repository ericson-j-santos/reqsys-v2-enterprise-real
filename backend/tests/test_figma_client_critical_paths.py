"""Testes de caminhos críticos — figma_client (HTTP, comentários e assinatura)."""

import hashlib
import hmac
import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services import figma_client as fc
from app.services.figma_client import FigmaError


def test_request_json_sem_token_levanta_erro(monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', '')

    with pytest.raises(FigmaError, match='FIGMA_ACCESS_TOKEN'):
        fc._request_json('GET', '/v1/files/demo')


@patch('app.services.figma_client.request.urlopen')
def test_request_json_http_error_propaga_figma_error(mock_urlopen, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_urlopen.side_effect = HTTPError('https://api.figma.com', 403, 'forbidden', {}, BytesIO(b'denied'))

    with pytest.raises(FigmaError, match='HTTP 403'):
        fc._request_json('GET', '/v1/files/demo')


@patch('app.services.figma_client.request.urlopen')
def test_request_json_url_error_propaga_figma_error(mock_urlopen, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_urlopen.side_effect = URLError('network down')

    with pytest.raises(FigmaError, match='Falha de rede'):
        fc._request_json('GET', '/v1/files/demo')


@patch('app.services.figma_client._request_json')
def test_get_file_e_get_nodes_delegam_request(mock_request, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_request.return_value = {'document': {'id': '0:0'}}

    file_payload = fc.get_file('file/key')
    nodes_payload = fc.get_nodes('file/key', ['1:2', '3:4'])

    assert file_payload['document']['id'] == '0:0'
    assert nodes_payload['document']['id'] == '0:0'
    assert mock_request.call_count == 2


@patch('app.services.figma_client._request_json')
def test_get_comments_retorna_lista_vazia_quando_ausente(mock_request, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_request.return_value = {}

    assert fc.get_comments('file-key') == []


@patch('app.services.figma_client._request_json')
def test_create_comment_inclui_node_id_quando_informado(mock_request, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_request.return_value = {'id': 'comment-1'}

    created = fc.create_comment('file-key', 'mensagem', node_id='12:34')

    assert created['id'] == 'comment-1'
    payload = mock_request.call_args.kwargs['payload']
    assert payload['client_meta']['node_id'] == '12:34'


def test_validate_webhook_signature_ignora_sem_secret(monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_webhook_secret', '')
    fc.validate_webhook_signature(b'{}', None)


def test_validate_webhook_signature_rejeita_ausente_com_secret(monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_webhook_secret', 'segredo')
    with pytest.raises(FigmaError, match='Assinatura Figma ausente'):
        fc.validate_webhook_signature(b'{}', None)


def test_validate_webhook_signature_compara_hmac(monkeypatch):
    secret = 'segredo-webhook'
    body = json.dumps({'event': 'FILE_UPDATE'}).encode('utf-8')
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    monkeypatch.setattr(fc.settings, 'figma_webhook_secret', secret)

    fc.validate_webhook_signature(body, f'sha256={expected}')

    with pytest.raises(FigmaError, match='invalida'):
        fc.validate_webhook_signature(body, 'sha256=deadbeef')
