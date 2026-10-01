"""OAuth client-credentials Microsoft com diagnostico seguro.

O modulo preserva apenas metadados operacionais allowlisted da resposta do
Microsoft Entra. Corpo completo, access token, client secret e identificadores
da App Registration nunca entram na excecao nem no retorno serializavel.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_AADSTS_PATTERN = re.compile(r'\bAADSTS\d+\b', re.IGNORECASE)
_SAFE_CODE_PATTERN = re.compile(r'[^A-Za-z0-9._-]')
_SAFE_ID_PATTERN = re.compile(r'[^A-Za-z0-9._:-]')


def _safe_text(value: object, *, identifier: bool = False, limit: int = 128) -> str | None:
    if value in (None, ''):
        return None
    raw = str(value).strip()[:limit]
    pattern = _SAFE_ID_PATTERN if identifier else _SAFE_CODE_PATTERN
    sanitized = pattern.sub('', raw)
    return sanitized or None


class MicrosoftOAuthError(RuntimeError):
    """Falha OAuth sanitizada e adequada para logs/retornos operacionais."""

    def __init__(
        self,
        *,
        resource: str,
        status_code: int | None,
        error_code: str,
        aadsts_code: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.resource = _safe_text(resource) or 'microsoft'
        self.status_code = status_code
        self.error_code = _safe_text(error_code) or 'oauth_token_error'
        self.aadsts_code = _safe_text(aadsts_code)
        self.trace_id = _safe_text(trace_id, identifier=True)
        self.correlation_id = _safe_text(correlation_id, identifier=True)
        self.timestamp = _safe_text(timestamp, identifier=True)
        super().__init__(self._safe_message())

    def _safe_message(self) -> str:
        markers = [self.error_code]
        if self.aadsts_code:
            markers.append(self.aadsts_code)
        marker_text = ', '.join(markers)
        status_text = f'HTTP {self.status_code}' if self.status_code is not None else 'falha de transporte'
        return f'Falha OAuth Microsoft Entra para {self.resource} ({status_text}; {marker_text})'

    def as_dict(self) -> dict[str, Any]:
        return {
            'type': 'oauth_token',
            'provider': 'microsoft_entra',
            'resource': self.resource,
            'status_code': self.status_code,
            'error_code': self.error_code,
            'aadsts_code': self.aadsts_code,
            'trace_id': self.trace_id,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp,
        }

    @classmethod
    def from_response(cls, response: httpx.Response, *, resource: str) -> MicrosoftOAuthError:
        payload: dict[str, Any] = {}
        try:
            raw_payload = response.json()
            if isinstance(raw_payload, dict):
                payload = raw_payload
        except (ValueError, TypeError):
            # Corpo não JSON é ignorado para evitar propagar conteúdo sensível.
            payload = {}

        description = str(payload.get('error_description') or '')
        aadsts_match = _AADSTS_PATTERN.search(description)
        aadsts_code = aadsts_match.group(0).upper() if aadsts_match else None
        if not aadsts_code:
            error_codes = payload.get('error_codes')
            if isinstance(error_codes, list) and error_codes:
                try:
                    aadsts_code = f'AADSTS{int(error_codes[0])}'
                except (TypeError, ValueError):
                    aadsts_code = None

        return cls(
            resource=resource,
            status_code=response.status_code,
            error_code=str(payload.get('error') or 'oauth_http_error'),
            aadsts_code=aadsts_code,
            trace_id=payload.get('trace_id'),
            correlation_id=payload.get('correlation_id'),
            timestamp=payload.get('timestamp'),
        )


async def acquire_client_credentials_token(
    *,
    client: httpx.AsyncClient,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scope: str,
    resource: str,
) -> str:
    """Adquire token app-only sem deixar material sensivel escapar em erros."""
    try:
        response = await client.post(
            _TOKEN_URL.format(tenant=tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': scope,
            },
        )
    except httpx.RequestError as exc:
        raise MicrosoftOAuthError(
            resource=resource,
            status_code=None,
            error_code='token_endpoint_unavailable',
        ) from exc

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MicrosoftOAuthError.from_response(response, resource=resource) from exc

    try:
        payload = response.json()
    except (ValueError, TypeError) as exc:
        raise MicrosoftOAuthError(
            resource=resource,
            status_code=response.status_code,
            error_code='invalid_token_response',
        ) from exc

    token = payload.get('access_token') if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise MicrosoftOAuthError(
            resource=resource,
            status_code=response.status_code,
            error_code='access_token_missing',
        )
    return token
