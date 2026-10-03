"""Fontes JSON versionadas: API HTTPS ou exportação atômica em diretório aprovado."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import get_type_hints
from urllib.parse import urlsplit

import requests

from app.services.movimento_email.models import (
    ItemFechamento,
    ItemPendenciaCadastro,
    ItemPendenciaHistorica,
    ItemPendenciaObservacao,
)
from app.services.movimento_email.repository import ExtracaoError

_DATASETS = {
    'fechamento': ItemFechamento,
    'pendencias_cadastro': ItemPendenciaCadastro,
    'pendencias_historicas': ItemPendenciaHistorica,
    'pendencias_observacao': ItemPendenciaObservacao,
}
MAX_BYTES = 5 * 1024 * 1024


class SnapshotRepository:
    """Uma instância por job; os quatro datasets vêm do mesmo snapshot validado."""

    def __init__(self, *, source_id: str, correlation_id: str, max_age_seconds: int = 86400):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', source_id) or max_age_seconds <= 0:
            raise ExtracaoError('Identificador da fonte e validade positiva são obrigatórios')
        self.source_id = source_id
        self.correlation_id = correlation_id
        self.max_age_seconds = max_age_seconds
        self._snapshot = None
        self.evidence: dict = {}

    def _read(self, reference: date) -> bytes:
        raise NotImplementedError

    def _load(self, reference: date):
        if self._snapshot is not None:
            if self.evidence['data_referencia'] != reference.isoformat():
                raise ExtracaoError('Snapshot não pode ser reutilizado para outra data')
            return self._snapshot
        raw = self._read(reference)
        try:
            if len(raw) > MAX_BYTES:
                raise ValueError
            payload = json.loads(raw.decode('utf-8'))
            expected = {'schema_version', 'source_id', 'data_referencia', 'generated_at', *_DATASETS}
            if not isinstance(payload, dict) or set(payload) != expected:
                raise ValueError
            if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
                raise ValueError
            if payload['source_id'] != self.source_id or payload['data_referencia'] != reference.isoformat():
                raise ValueError
            generated = datetime.fromisoformat(payload['generated_at'].replace('Z', '+00:00'))
            if generated.tzinfo is None:
                raise ValueError
            age = (datetime.now(timezone.utc) - generated).total_seconds()
            if age < -300 or age > self.max_age_seconds:
                raise ValueError
            snapshot = {}
            for name, model in _DATASETS.items():
                rows = payload[name]
                if not isinstance(rows, list) or len(rows) > 10000:
                    raise ValueError
                hints = get_type_hints(model)
                allowed = {field.name for field in fields(model)}
                result = []
                for row in rows:
                    if not isinstance(row, dict) or set(row) - allowed:
                        raise ValueError
                    for key, value in row.items():
                        expected_type = hints[key]
                        if type(value) is not expected_type and not (expected_type is float and type(value) is int):
                            raise ValueError
                        if isinstance(value, str) and len(value) > 10000:
                            raise ValueError
                        if isinstance(value, (int, float)) and (value < 0 or not math.isfinite(value)):
                            raise ValueError
                    result.append(model(**row))
                snapshot[name] = result
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
            raise ExtracaoError('Snapshot inválido, vencido ou incompatível com a fonte/data solicitada') from None
        self.evidence = {
            'source_id': self.source_id,
            'schema_version': 1,
            'data_referencia': reference.isoformat(),
            'generated_at': generated.isoformat(),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'correlation_id': self.correlation_id,
        }
        self._snapshot = snapshot
        return snapshot

    def get_fechamento(self, data_referencia: date):
        return self._load(data_referencia)['fechamento']

    def get_pendencias_cadastro(self, data_referencia: date):
        return self._load(data_referencia)['pendencias_cadastro']

    def get_pendencias_historicas(self, data_referencia: date):
        return self._load(data_referencia)['pendencias_historicas']

    def get_pendencias_observacao(self, data_referencia: date):
        return self._load(data_referencia)['pendencias_observacao']


class FileSnapshotRepository(SnapshotRepository):
    def __init__(self, *, directory: str, **kwargs):
        super().__init__(**kwargs)
        if not directory:
            raise ExtracaoError('Diretório de exportações não configurado')
        self.directory = Path(directory).resolve()

    def _read(self, reference: date) -> bytes:
        try:
            target = (self.directory / f'{reference.isoformat()}.json').resolve()
            if target.parent != self.directory:
                raise ExtracaoError('Arquivo fora do diretório aprovado')
            with target.open('rb') as handle:
                return handle.read(MAX_BYTES + 1)
        except OSError:
            raise ExtracaoError('Exportação indisponível no diretório aprovado') from None


class ApiSnapshotRepository(SnapshotRepository):
    def __init__(self, *, url: str, token: str, timeout_seconds: float = 30, **kwargs):
        super().__init__(**kwargs)
        try:
            parsed = urlsplit(url)
        except ValueError:
            raise ExtracaoError('URL da API inv?lida') from None
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ExtracaoError('API exige URL HTTPS fixa, sem credenciais, query ou fragmento')
        if not token or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ExtracaoError('Token da API e timeout positivo são obrigatórios')
        self.url, self.token, self.timeout_seconds = url, token, timeout_seconds

    def _read(self, reference: date) -> bytes:
        try:
            with requests.get(
                self.url, params={'data_referencia': reference.isoformat()},
                headers={'Authorization': f'Bearer {self.token}', 'X-Correlation-ID': self.correlation_id},
                timeout=self.timeout_seconds, allow_redirects=False, stream=True,
            ) as response:
                if response.status_code != 200:
                    raise ExtracaoError('API de origem não retornou HTTP 200')
                raw = bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        raise ExtracaoError('Snapshot excede o limite de tamanho')
                return bytes(raw)
        except requests.RequestException:
            raise ExtracaoError('Falha de comunicação com a API de origem') from None
