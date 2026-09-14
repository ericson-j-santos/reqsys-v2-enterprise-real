"""Ingestão governada de anexos Redmine para o bounded context OCR.

A integração mantém o Redmine como origem remota e materializa apenas cópias
sanitizadas sob ``OCR_INPUT_ROOT``. O nome original do anexo não é persistido no
caminho de entrada, evitando exposição desnecessária de PII em logs/auditoria.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from app.core.secrets import get_secret

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = frozenset({'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'})
_TYPE_BY_EXTENSION = {
    '.pdf': 'REDMINE_PDF',
    '.png': 'REDMINE_IMAGEM',
    '.jpg': 'REDMINE_IMAGEM',
    '.jpeg': 'REDMINE_IMAGEM',
    '.tif': 'REDMINE_IMAGEM',
    '.tiff': 'REDMINE_IMAGEM',
    '.bmp': 'REDMINE_IMAGEM',
}


class RedmineAttachmentError(RuntimeError):
    """Falha segura na leitura/materialização de um anexo Redmine."""


class RedmineAttachmentUnsupported(RedmineAttachmentError):
    """Anexo válido no Redmine, mas fora dos formatos aceitos pelo OCR atual."""


@dataclass(frozen=True)
class RedmineAttachment:
    attachment_id: int
    filename: str
    content_url: str
    content_type: str = ''
    filesize: int | None = None


@dataclass(frozen=True)
class ImportedRedmineAttachment:
    issue_id: int
    attachment_id: int
    document_ref: str
    sha256: str
    size_bytes: int
    tipo_documento: str


class RedmineAttachmentClient:
    """Cliente mínimo e fail-closed para anexos da API REST do Redmine."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
        max_bytes: int | None = None,
    ) -> None:
        self.base_url = (base_url or get_secret('REDMINE_BASE_URL', '') or '').strip().rstrip('/')
        self.api_key = (api_key or get_secret('REDMINE_API_KEY', '') or '').strip()
        self.timeout_seconds = float(timeout_seconds)
        configured_limit = max_bytes
        if configured_limit is None:
            raw_limit = (os.getenv('OCR_REDMINE_MAX_BYTES') or '').strip()
            configured_limit = int(raw_limit) if raw_limit.isdigit() else DEFAULT_MAX_BYTES
        self.max_bytes = int(configured_limit)

        parsed = urlparse(self.base_url)
        if not self.base_url or not self.api_key:
            raise RedmineAttachmentError(
                'Redmine não configurado. Defina REDMINE_BASE_URL e REDMINE_API_KEY.'
            )
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise RedmineAttachmentError('REDMINE_BASE_URL inválida')
        if self.max_bytes < 1:
            raise RedmineAttachmentError('OCR_REDMINE_MAX_BYTES deve ser maior que zero')
        self._origin = (parsed.scheme.lower(), parsed.netloc.lower())

    def list_attachments(self, issue_id: int) -> list[RedmineAttachment]:
        issue_id = _validated_positive_id(issue_id, 'issue_id')
        query = parse.urlencode({'include': 'attachments'})
        payload = self._get_json(f'{self.base_url}/issues/{issue_id}.json?{query}')
        issue = payload.get('issue') if isinstance(payload, dict) else None
        if not isinstance(issue, dict):
            raise RedmineAttachmentError('Resposta do Redmine sem objeto issue')

        attachments: list[RedmineAttachment] = []
        for item in issue.get('attachments') or []:
            if not isinstance(item, dict):
                continue
            try:
                attachment_id = _validated_positive_id(item.get('id'), 'attachment_id')
            except RedmineAttachmentError:
                continue
            content_url = str(item.get('content_url') or '').strip()
            filename = str(item.get('filename') or '').strip()
            if not content_url or not filename:
                continue
            filesize = item.get('filesize')
            parsed_size: int | None = None
            if filesize not in (None, ''):
                try:
                    parsed_size = int(filesize)
                except (TypeError, ValueError):
                    raise RedmineAttachmentError(
                        f'filesize inválido no anexo {attachment_id}'
                    ) from None
            attachments.append(
                RedmineAttachment(
                    attachment_id=attachment_id,
                    filename=filename,
                    content_url=content_url,
                    content_type=str(item.get('content_type') or '').strip(),
                    filesize=parsed_size,
                )
            )
        return attachments

    def import_attachment(
        self,
        issue_id: int,
        attachment: RedmineAttachment,
        *,
        input_root: str | Path,
    ) -> ImportedRedmineAttachment:
        issue_id = _validated_positive_id(issue_id, 'issue_id')
        attachment_id = _validated_positive_id(attachment.attachment_id, 'attachment_id')
        suffix = Path(attachment.filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise RedmineAttachmentUnsupported(
                f'formato não suportado pelo OCR: {suffix or "sem extensão"}'
            )
        if attachment.filesize is not None:
            if attachment.filesize < 0:
                raise RedmineAttachmentError(f'filesize inválido no anexo {attachment_id}')
            if attachment.filesize > self.max_bytes:
                raise RedmineAttachmentError(
                    f'anexo {attachment_id} excede limite de {self.max_bytes} bytes'
                )

        download_url = parse.urljoin(f'{self.base_url}/', attachment.content_url)
        self._assert_same_origin(download_url)
        data = self._get_bytes(download_url)
        _validate_signature(data, suffix, attachment_id)

        digest = hashlib.sha256(data).hexdigest()
        root = Path(input_root).resolve()
        target_dir = (root / 'redmine' / str(issue_id)).resolve()
        if not target_dir.is_relative_to(root):
            raise RedmineAttachmentError('destino do anexo escapou do OCR_INPUT_ROOT')
        target_dir.mkdir(parents=True, exist_ok=True)
        target = (target_dir / f'attachment-{attachment_id}-{digest[:16]}{suffix}').resolve()
        if not target.is_relative_to(root):
            raise RedmineAttachmentError('destino do anexo escapou do OCR_INPUT_ROOT')

        if target.exists():
            if not target.is_file():
                raise RedmineAttachmentError('destino idempotente existe e não é arquivo')
            current_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if current_digest != digest:
                raise RedmineAttachmentError('colisão de destino idempotente detectada')
        else:
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='wb',
                    dir=target_dir,
                    prefix='.redmine-attachment-',
                    suffix='.part',
                    delete=False,
                ) as tmp:
                    tmp.write(data)
                    tmp.flush()
                    temp_path = Path(tmp.name)
                os.replace(temp_path, target)
            finally:
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink(missing_ok=True)

        return ImportedRedmineAttachment(
            issue_id=issue_id,
            attachment_id=attachment_id,
            document_ref=target.relative_to(root).as_posix(),
            sha256=digest,
            size_bytes=len(data),
            tipo_documento=_TYPE_BY_EXTENSION[suffix],
        )

    def _headers(self) -> dict[str, str]:
        return {
            'User-Agent': 'reqsys-ocr-redmine/1.0',
            'Accept': 'application/json',
            'X-Redmine-API-Key': self.api_key,
        }

    def _assert_same_origin(self, url: str) -> None:
        parsed = urlparse(url)
        origin = (parsed.scheme.lower(), parsed.netloc.lower())
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or origin != self._origin:
            raise RedmineAttachmentError('content_url do anexo aponta para origem não autorizada')

    def _get_json(self, url: str) -> dict:
        self._assert_same_origin(url)
        req = request.Request(url=url, headers=self._headers(), method='GET')
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec B310
                self._assert_same_origin(resp.geturl())
                raw = resp.read(self.max_bytes + 1)
        except HTTPError as exc:
            raise RedmineAttachmentError(f'Redmine HTTP {exc.code} ao consultar anexos') from exc
        except URLError as exc:
            raise RedmineAttachmentError(f'Falha de rede ao consultar Redmine: {exc.reason}') from exc
        if len(raw) > self.max_bytes:
            raise RedmineAttachmentError('resposta JSON do Redmine excedeu o limite configurado')
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RedmineAttachmentError('Resposta JSON inválida do Redmine') from exc
        if not isinstance(payload, dict):
            raise RedmineAttachmentError('Resposta JSON inesperada do Redmine')
        return payload

    def _get_bytes(self, url: str) -> bytes:
        self._assert_same_origin(url)
        headers = self._headers()
        headers['Accept'] = 'application/octet-stream,application/pdf,image/*'
        req = request.Request(url=url, headers=headers, method='GET')
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec B310
                self._assert_same_origin(resp.geturl())
                content_length = resp.headers.get('Content-Length')
                if content_length:
                    try:
                        if int(content_length) > self.max_bytes:
                            raise RedmineAttachmentError(
                                f'anexo excede limite de {self.max_bytes} bytes'
                            )
                    except ValueError:
                        pass
                data = resp.read(self.max_bytes + 1)
        except HTTPError as exc:
            raise RedmineAttachmentError(f'Redmine HTTP {exc.code} ao baixar anexo') from exc
        except URLError as exc:
            raise RedmineAttachmentError(f'Falha de rede ao baixar anexo Redmine: {exc.reason}') from exc
        if len(data) > self.max_bytes:
            raise RedmineAttachmentError(f'anexo excede limite de {self.max_bytes} bytes')
        if not data:
            raise RedmineAttachmentError('anexo Redmine vazio')
        return data


def _validated_positive_id(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RedmineAttachmentError(f'{field_name} inválido') from exc
    if parsed < 1:
        raise RedmineAttachmentError(f'{field_name} deve ser maior que zero')
    return parsed


def _validate_signature(data: bytes, suffix: str, attachment_id: int) -> None:
    valid = False
    if suffix == '.pdf':
        valid = data.startswith(b'%PDF-')
    elif suffix == '.png':
        valid = data.startswith(b'\x89PNG\r\n\x1a\n')
    elif suffix in {'.jpg', '.jpeg'}:
        valid = data.startswith(b'\xff\xd8\xff')
    elif suffix in {'.tif', '.tiff'}:
        valid = data.startswith((b'II*\x00', b'MM\x00*'))
    elif suffix == '.bmp':
        valid = data.startswith(b'BM')
    if not valid:
        raise RedmineAttachmentError(
            f'assinatura binária incompatível com a extensão do anexo {attachment_id}'
        )
