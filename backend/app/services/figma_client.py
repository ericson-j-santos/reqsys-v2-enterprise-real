import hashlib
import hmac
import json
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.core.config import settings


class FigmaError(RuntimeError):
    pass


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    token = (settings.figma_access_token or '').strip()
    if not token:
        raise FigmaError('FIGMA_ACCESS_TOKEN nao configurado.')

    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {
        'Accept': 'application/json',
        'X-Figma-Token': token,
        'User-Agent': 'reqsys-figma-github-sync/1.0',
    }
    if body is not None:
        headers['Content-Type'] = 'application/json'

    req = request.Request(url=f'https://api.figma.com{path}', data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:  # nosec B310
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise FigmaError(f'HTTP {exc.code} no Figma: {detail[:400]}') from exc
    except URLError as exc:
        raise FigmaError(f'Falha de rede no Figma: {exc.reason}') from exc


def get_file(file_key: str) -> dict[str, Any]:
    return _request_json('GET', f'/v1/files/{parse.quote(file_key, safe="")}')


def get_nodes(file_key: str, node_ids: list[str]) -> dict[str, Any]:
    ids = ','.join(node_ids)
    return _request_json('GET', f'/v1/files/{parse.quote(file_key, safe="")}/nodes?ids={parse.quote(ids)}')


def get_comments(file_key: str) -> list[dict[str, Any]]:
    payload = _request_json('GET', f'/v1/files/{parse.quote(file_key, safe="")}/comments')
    return payload.get('comments') or []


def create_comment(file_key: str, message: str, node_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {'message': message}
    if node_id:
        payload['client_meta'] = {'node_id': node_id}
    return _request_json('POST', f'/v1/files/{parse.quote(file_key, safe="")}/comments', payload=payload)


def validate_webhook_signature(body: bytes, signature: str | None) -> None:
    secret = (settings.figma_webhook_secret or '').strip()
    if not secret:
        return
    if not signature:
        raise FigmaError('Assinatura Figma ausente.')
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    normalized = signature.removeprefix('sha256=')
    if not hmac.compare_digest(normalized, expected):
        raise FigmaError('Assinatura Figma invalida.')
