"""Envio de e-mail pelo Microsoft Graph usando identidade de aplicação.

Usa OAuth 2.0 client credentials com as credenciais Microsoft Entra já
configuradas no ReqSys. O conteúdo é enviado como MIME para preservar HTML,
texto alternativo e cabeçalhos de correlação existentes.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import requests

from app.core.resilience import CircuitBreaker, call_with_retry
from app.services.movimento_email.smtp_sender import EnvioEmailError

logger = logging.getLogger('reqsys.movimento_email.graph')

_CIRCUIT = CircuitBreaker(name='movimento_email_graph', failure_threshold=3, cooldown_seconds=60)
_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class GraphEmailSender:
    """Envia mensagens via Microsoft Graph sem sessão de usuário interativa."""

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        sender_user: str,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        obrigatorios = {
            'AZURE_TENANT_ID': tenant_id,
            'AZURE_CLIENT_ID': client_id,
            'AZURE_CLIENT_SECRET': client_secret,
            'MOVIMENTO_EMAIL_GRAPH_SENDER': sender_user,
        }
        faltantes = [nome for nome, valor in obrigatorios.items() if not str(valor or '').strip()]
        if faltantes:
            raise EnvioEmailError('Microsoft Graph não configurado: ' + ', '.join(faltantes))

        self._tenant_id = tenant_id.strip()
        self._client_id = client_id.strip()
        self._client_secret = client_secret
        self._sender_user = sender_user.strip()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._http_post = http_post or requests.post

    @property
    def sender_user(self) -> str:
        return self._sender_user

    def _obter_token(self) -> str:
        url = f'https://login.microsoftonline.com/{quote(self._tenant_id, safe="")}/oauth2/v2.0/token'
        response = self._http_post(
            url,
            data={
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials',
            },
            timeout=self._timeout_seconds,
        )
        if response.status_code in _TRANSIENT_STATUS:
            raise requests.RequestException(f'identidade Microsoft indisponível: HTTP {response.status_code}')
        if response.status_code >= 400:
            raise EnvioEmailError(f'identidade Microsoft rejeitou autenticação: HTTP {response.status_code}')

        try:
            token = str(response.json().get('access_token') or '')
        except (TypeError, ValueError) as exc:
            raise EnvioEmailError('resposta de autenticação Microsoft inválida') from exc
        if not token:
            raise EnvioEmailError('resposta de autenticação Microsoft sem access_token')
        return token

    def _enviar_uma_vez(self, message: EmailMessage) -> None:
        token = self._obter_token()
        mime_b64 = base64.b64encode(message.as_bytes()).decode('ascii')
        sender_encoded = quote(self._sender_user, safe='')
        response = self._http_post(
            f'https://graph.microsoft.com/v1.0/users/{sender_encoded}/sendMail',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'text/plain',
            },
            data=mime_b64,
            timeout=self._timeout_seconds,
        )
        if response.status_code == 202:
            return
        if response.status_code in _TRANSIENT_STATUS:
            raise requests.RequestException(f'Microsoft Graph temporariamente indisponível: HTTP {response.status_code}')

        codigo = ''
        try:
            payload = response.json()
            codigo = str((payload.get('error') or {}).get('code') or '')[:80]
        except (TypeError, ValueError, AttributeError):
            codigo = ''
        detalhe = f' código={codigo}' if codigo else ''
        raise EnvioEmailError(f'Microsoft Graph rejeitou envio: HTTP {response.status_code}{detalhe}')

    def enviar(self, message: EmailMessage) -> None:
        try:
            call_with_retry(
                lambda: self._enviar_uma_vez(message),
                max_retries=self._max_retries,
                backoff_seconds=1.0,
                retry_on=(requests.RequestException,),
                circuit=_CIRCUIT,
            )
        except requests.RequestException as exc:
            logger.error('movimento_email_graph_falhou tipo=%s', type(exc).__name__)
            raise EnvioEmailError('falha transitória ao enviar e-mail pelo Microsoft Graph') from exc
