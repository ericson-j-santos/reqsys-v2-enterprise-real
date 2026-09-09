from __future__ import annotations

import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.services.vba_legacy_analyzer import analyze_vba_source

SUPPORTED_EXTENSIONS = {'.bas', '.cls', '.frm', '.vba', '.txt'}
BINARY_MACRO_EXTENSIONS = {'.xlsm', '.xlsb', '.xlam', '.docm', '.dotm'}
DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024

router = APIRouter(prefix='/legado/vba', tags=['Análise de legado VBA'])


def _safe_name(file_name: str | None) -> str:
    value = (file_name or 'module.bas').strip()
    return re.split(r'[/\\]', value)[-1] or 'module.bas'


def _suffix(file_name: str) -> str:
    match = re.search(r'(\.[A-Za-z0-9]+)$', file_name)
    return match.group(1).lower() if match else ''


def _max_upload_bytes() -> int:
    raw = (os.getenv('VBA_ANALYZER_MAX_UPLOAD_BYTES') or '').strip()
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return value if value > 0 else DEFAULT_MAX_UPLOAD_BYTES


def _decode_source(content: bytes) -> str:
    if b'\x00' in content:
        raise ValueError('VBA_SOURCE_BINARY_CONTENT')
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('VBA_SOURCE_ENCODING_UNSUPPORTED')


def _validate_file(file_name: str, content: bytes) -> None:
    extension = _suffix(file_name)
    if extension in BINARY_MACRO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                'code': 'VBA_BINARY_CONTAINER_NOT_SUPPORTED',
                'message': 'Exporte os módulos VBA como .bas, .cls ou .frm para análise estática.',
                'next_increment': 'extração governada de vbaProject.bin de contêineres Office',
            },
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                'code': 'VBA_SOURCE_EXTENSION_UNSUPPORTED',
                'supported_extensions': sorted(SUPPORTED_EXTENSIONS),
            },
        )
    if not content:
        raise HTTPException(status_code=422, detail={'code': 'VBA_SOURCE_EMPTY'})
    max_bytes = _max_upload_bytes()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                'code': 'VBA_SOURCE_TOO_LARGE',
                'max_bytes': max_bytes,
            },
        )


@router.get('/readiness')
def vba_analyzer_readiness(user: dict = Depends(require_admin)):
    del user
    return ok(
        {
            'ready': True,
            'analysis_type': 'static_only',
            'execution_performed': False,
            'supported_extensions': sorted(SUPPORTED_EXTENSIONS),
            'binary_containers_supported': False,
            'max_upload_bytes': _max_upload_bytes(),
        }
    )


@router.post('/analisar')
async def analyze_vba_upload(
    arquivo: UploadFile = File(...),
    user: dict = Depends(require_admin),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-Id'),
):
    del user
    file_name = _safe_name(arquivo.filename)
    content = await arquivo.read()
    _validate_file(file_name, content)
    try:
        source = _decode_source(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={'code': str(exc)}) from None

    fallback_correlation_id = str(uuid4())
    correlation_id = resolver_correlation_id(x_correlation_id, fallback_correlation_id)
    analysis = analyze_vba_source(source, file_name=file_name)
    return ok(
        analysis,
        correlation_id,
        meta={
            'idempotent_analysis': True,
            'source_persisted': False,
        },
    )
