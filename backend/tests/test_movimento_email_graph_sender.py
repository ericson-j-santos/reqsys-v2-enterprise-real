from __future__ import annotations

import base64
from email.message import EmailMessage

import pytest
import requests

from app.services.movimento_email.graph_sender import GraphEmailSender
from app.services.movimento_email.smtp_sender import EnvioEmailError


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _mensagem() -> EmailMessage:
    message = EmailMessage()
    message['From'] = 'reqsys@empresa.test'
    message['To'] = 'destino@empresa.test'
    message['Subject'] = 'Teste Graph'
    message['X-Correlation-ID'] = 'corr-123'
    message.set_content('texto')
    message.add_alternative('<p>html</p>', subtype='html')
    return message


def _sender_com_post(http_post):
    return GraphEmailSender(
        tenant_id='tenant-123',
        client_id='client-123',
        client_secret='segredo',
        sender_user='reqsys@empresa.test',
        http_post=http_post,
    )


def test_graph_sender_obtem_token_e_envia_mime():
    chamadas: list[dict] = []

    def fake_post(url, **kwargs):
        chamadas.append({'url': url, **kwargs})
        if url.endswith('/oauth2/v2.0/token'):
            return _Response(200, {'access_token': 'token-teste'})
        return _Response(202)

    sender = _sender_com_post(fake_post)

    sender.enviar(_mensagem())

    assert len(chamadas) == 2
    assert chamadas[0]['data']['scope'] == 'https://graph.microsoft.com/.default'
    assert chamadas[0]['data']['grant_type'] == 'client_credentials'
    assert chamadas[1]['url'].endswith('/v1.0/users/reqsys%40empresa.test/sendMail')
    assert chamadas[1]['headers']['Authorization'] == 'Bearer token-teste'
    mime = base64.b64decode(chamadas[1]['data']).decode('utf-8', errors='replace')
    assert 'X-Correlation-ID: corr-123' in mime
    assert 'Subject: Teste Graph' in mime


def test_graph_sender_nao_expoe_corpo_de_erro_do_graph():
    def fake_post(url, **kwargs):
        if url.endswith('/oauth2/v2.0/token'):
            return _Response(200, {'access_token': 'token-teste'})
        return _Response(403, {'error': {'code': 'ErrorAccessDenied', 'message': 'segredo-interno'}})

    sender = _sender_com_post(fake_post)

    with pytest.raises(EnvioEmailError) as exc_info:
        sender.enviar(_mensagem())

    detalhe = str(exc_info.value)
    assert 'ErrorAccessDenied' in detalhe
    assert 'segredo-interno' not in detalhe
    assert 'segredo' not in detalhe


def test_graph_sender_rejeita_configuracao_incompleta():
    with pytest.raises(EnvioEmailError) as exc_info:
        GraphEmailSender(
            tenant_id='',
            client_id='client-123',
            client_secret='segredo',
            sender_user='reqsys@empresa.test',
        )

    assert 'AZURE_TENANT_ID' in str(exc_info.value)


@pytest.mark.parametrize(
    ('status_code', 'erro_esperado'),
    [
        (503, requests.RequestException),
        (401, EnvioEmailError),
    ],
)
def test_graph_sender_classifica_falha_de_autenticacao(status_code, erro_esperado):
    sender = _sender_com_post(lambda *_args, **_kwargs: _Response(status_code))

    with pytest.raises(erro_esperado):
        sender._obter_token()


def test_graph_sender_rejeita_json_invalido_na_autenticacao():
    class _InvalidJsonResponse:
        status_code = 200

        def json(self):
            raise ValueError('json inválido')

    sender = _sender_com_post(lambda *_args, **_kwargs: _InvalidJsonResponse())

    with pytest.raises(EnvioEmailError, match='resposta de autenticação Microsoft inválida'):
        sender._obter_token()


def test_graph_sender_rejeita_token_ausente_na_autenticacao():
    sender = _sender_com_post(lambda *_args, **_kwargs: _Response(200, {}))

    with pytest.raises(EnvioEmailError, match='sem access_token'):
        sender._obter_token()
