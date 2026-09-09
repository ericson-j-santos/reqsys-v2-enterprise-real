from __future__ import annotations

import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.services.vba_legacy_analyzer import analyze_vba_source
from app.services.vba_office_container import (
    OFFICE_CONTAINER_EXTENSIONS,
    OfficeVbaContainerError,
    analyze_office_vba_container,
    office_container_readiness,
)

SUPPORTED_EXTENSIONS = {'.bas', '.cls', '.frm', '.vba', '.txt'}
DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_CONTAINER_BYTES = 16 * 1024 * 1024

router = APIRouter(prefix='/legado/vba', tags=['Análise de legado VBA'])


def _safe_name(file_name: str | None) -> str:
    value = (file_name or 'module.bas').strip()
    return re.split(r'[/\\]', value)[-1] or 'module.bas'


def _suffix(file_name: str) -> str:
    match = re.search(r'(\.[A-Za-z0-9]+)$', file_name)
    return match.group(1).lower() if match else ''


def _positive_env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _max_upload_bytes() -> int:
    return _positive_env_int('VBA_ANALYZER_MAX_UPLOAD_BYTES', DEFAULT_MAX_UPLOAD_BYTES)


def _max_container_bytes() -> int:
    return _positive_env_int('VBA_ANALYZER_MAX_CONTAINER_BYTES', DEFAULT_MAX_CONTAINER_BYTES)


def _decode_source(content: bytes) -> str:
    if b'\x00' in content:
        raise ValueError('VBA_SOURCE_BINARY_CONTENT')
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('VBA_SOURCE_ENCODING_UNSUPPORTED')


def _validate_file(file_name: str, content: bytes) -> str:
    extension = _suffix(file_name)
    if extension not in SUPPORTED_EXTENSIONS | OFFICE_CONTAINER_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                'code': 'VBA_INPUT_EXTENSION_UNSUPPORTED',
                'supported_extensions': sorted(SUPPORTED_EXTENSIONS | OFFICE_CONTAINER_EXTENSIONS),
            },
        )
    if not content:
        raise HTTPException(status_code=422, detail={'code': 'VBA_INPUT_EMPTY'})

    max_bytes = _max_container_bytes() if extension in OFFICE_CONTAINER_EXTENSIONS else _max_upload_bytes()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                'code': 'VBA_INPUT_TOO_LARGE',
                'max_bytes': max_bytes,
                'input_kind': 'office_container' if extension in OFFICE_CONTAINER_EXTENSIONS else 'source',
            },
        )
    return extension


@router.get('/readiness')
def vba_analyzer_readiness(user: dict = Depends(require_admin)):
    del user
    container = office_container_readiness()
    return ok(
        {
            'ready': True,
            'analysis_type': 'static_only',
            'execution_performed': False,
            'supported_source_extensions': sorted(SUPPORTED_EXTENSIONS),
            'supported_office_extensions': sorted(OFFICE_CONTAINER_EXTENSIONS),
            'office_container_ready': container['ready'],
            'office_parser': container,
            'max_upload_bytes': _max_upload_bytes(),
            'max_container_bytes': _max_container_bytes(),
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
    extension = _validate_file(file_name, content)

    fallback_correlation_id = str(uuid4())
    correlation_id = resolver_correlation_id(x_correlation_id, fallback_correlation_id)

    if extension in OFFICE_CONTAINER_EXTENSIONS:
        try:
            analysis = analyze_office_vba_container(content, file_name=file_name)
        except OfficeVbaContainerError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={'code': exc.code, **exc.context},
            ) from None
    else:
        try:
            source = _decode_source(content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={'code': str(exc)}) from None
        analysis = analyze_vba_source(source, file_name=file_name)

    return ok(
        analysis,
        correlation_id,
        meta={
            'idempotent_analysis': True,
            'source_persisted': False,
            'execution_performed': False,
        },
    )
