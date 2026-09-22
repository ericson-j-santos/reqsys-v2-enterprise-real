from __future__ import annotations

import json
import os
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class ProviderTelemetry:
    """Telemetry in-process, sem persistir prompt, resposta, PII ou segredo."""

    total_requisicoes: int = 0
    sucessos: int = 0
    falhas: int = 0
    fallback_acionado: int = 0
    ultima_chamada_em: str | None = None
    ultimo_sucesso_em: str | None = None
    ultima_falha_em: str | None = None
    ultimo_tipo_erro: str | None = None

    def snapshot(self) -> dict[str, Any]:
        taxa_sucesso = 0.0
        if self.total_requisicoes:
            taxa_sucesso = round((self.sucessos / self.total_requisicoes) * 100, 2)
        return {
            'total_requisicoes': self.total_requisicoes,
            'sucessos': self.sucessos,
            'falhas': self.falhas,
            'fallback_acionado': self.fallback_acionado,
            'taxa_sucesso_pct': taxa_sucesso,
            'ultima_chamada_em': self.ultima_chamada_em,
            'ultimo_sucesso_em': self.ultimo_sucesso_em,
            'ultima_falha_em': self.ultima_falha_em,
            'ultimo_tipo_erro': self.ultimo_tipo_erro,
        }


_lock = threading.Lock()
_telemetry: dict[str, ProviderTelemetry] = defaultdict(ProviderTelemetry)

_TELEMETRY_STORE_PATH_ENV = 'REQSYS_LLM_TELEMETRY_STORE_PATH'
_TELEMETRY_RETENTION_DAYS_ENV = 'REQSYS_LLM_TELEMETRY_RETENTION_DAYS'
_DEFAULT_STORE_PATH = Path('artifacts/runtime/llm-telemetry.jsonl')
_DEFAULT_RETENTION_DAYS = 30
_SUPPORTED_STATUSES = {'sucesso', 'falha', 'fallback_acionado'}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _agora_iso() -> str:
    return _agora().isoformat()


def _store_path() -> Path:
    configured = os.getenv(_TELEMETRY_STORE_PATH_ENV, '').strip()
    return Path(configured) if configured else _DEFAULT_STORE_PATH


def _retention_days() -> int:
    raw = os.getenv(_TELEMETRY_RETENTION_DAYS_ENV, '').strip()
    if not raw:
        return _DEFAULT_RETENTION_DAYS
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_RETENTION_DAYS


def _sanitize_provider(provider: str) -> str:
    return (provider or 'desconhecido').strip().lower() or 'desconhecido'


def _sanitize_status(status: str) -> str:
    return (status or '').strip().lower()


def _event_record(provider: str, status: str, tipo_erro: str | None, occurred_at: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        'event_id': str(uuid.uuid4()),
        'occurred_at': occurred_at,
        'provider': provider,
        'status': status,
        'schema_version': '1.0',
        'contains_prompt': False,
        'contains_response': False,
        'contains_secret': False,
        'governance': {
            'classification': 'operational_telemetry',
            'pii': False,
            'append_only': True,
        },
    }
    if status == 'falha':
        record['tipo_erro'] = tipo_erro or 'erro_indisponivel'
    return record


def _append_event(record: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _iter_persisted_events() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def compactar_telemetry_llm() -> dict[str, Any]:
    """Remove eventos persistidos fora da janela de retenção, preservando append-only lógico por janela."""
    path = _store_path()
    events = _iter_persisted_events()
    cutoff = _agora() - timedelta(days=_retention_days())
    retained = []

    for event in events:
        occurred_at = _parse_iso(str(event.get('occurred_at', '')))
        if occurred_at and occurred_at >= cutoff:
            retained.append(event)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for event in retained:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')

    return {
        'store_path': str(path),
        'retention_days': _retention_days(),
        'eventos_antes': len(events),
        'eventos_retidos': len(retained),
        'eventos_removidos': max(0, len(events) - len(retained)),
    }


def registrar_evento_llm(provider: str, status: str, tipo_erro: str | None = None) -> None:
    """
    Registra evento operacional de LLM sem capturar payload sensível.

    Status suportados:
    - sucesso
    - falha
    - fallback_acionado
    """
    nome_provider = _sanitize_provider(provider)
    status_normalizado = _sanitize_status(status)
    if status_normalizado not in _SUPPORTED_STATUSES:
        return

    agora = _agora_iso()

    with _lock:
        item = _telemetry[nome_provider]
        if status_normalizado in {'sucesso', 'falha'}:
            item.total_requisicoes += 1
            item.ultima_chamada_em = agora
        if status_normalizado == 'sucesso':
            item.sucessos += 1
            item.ultimo_sucesso_em = agora
        elif status_normalizado == 'falha':
            item.falhas += 1
            item.ultima_falha_em = agora
            item.ultimo_tipo_erro = tipo_erro or 'erro_indisponivel'
        elif status_normalizado == 'fallback_acionado':
            item.fallback_acionado += 1

        record = _event_record(nome_provider, status_normalizado, tipo_erro, agora)
        _append_event(record)


def obter_snapshot_telemetry_llm() -> dict[str, Any]:
    """Retorna snapshot serializável para status, health checks e dashboards."""
    with _lock:
        return {provider: telemetry.snapshot() for provider, telemetry in sorted(_telemetry.items())}


def obter_telemetry_persistida_llm() -> dict[str, Any]:
    """Retorna resumo histórico persistido, sem expor payload sensível."""
    events = _iter_persisted_events()
    por_provider: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'total_eventos': 0,
        'sucessos': 0,
        'falhas': 0,
        'fallback_acionado': 0,
        'primeiro_evento_em': None,
        'ultimo_evento_em': None,
        'ultimo_tipo_erro': None,
    })

    for event in events:
        provider = _sanitize_provider(str(event.get('provider', 'desconhecido')))
        status = _sanitize_status(str(event.get('status', '')))
        occurred_at = event.get('occurred_at')
        item = por_provider[provider]
        item['total_eventos'] += 1
        if status == 'sucesso':
            item['sucessos'] += 1
        elif status == 'falha':
            item['falhas'] += 1
            item['ultimo_tipo_erro'] = event.get('tipo_erro') or 'erro_indisponivel'
        elif status == 'fallback_acionado':
            item['fallback_acionado'] += 1
        if occurred_at:
            if item['primeiro_evento_em'] is None or str(occurred_at) < str(item['primeiro_evento_em']):
                item['primeiro_evento_em'] = occurred_at
            if item['ultimo_evento_em'] is None or str(occurred_at) > str(item['ultimo_evento_em']):
                item['ultimo_evento_em'] = occurred_at

    for item in por_provider.values():
        requisicoes = item['sucessos'] + item['falhas']
        item['taxa_sucesso_pct'] = round((item['sucessos'] / requisicoes) * 100, 2) if requisicoes else 0.0

    path = _store_path()
    return {
        'store': {
            'tipo': 'jsonl_append_only',
            'path': str(path),
            'retention_days': _retention_days(),
            'existe': path.exists(),
        },
        'seguranca': {
            'sem_prompt': True,
            'sem_resposta': True,
            'sem_chaves': True,
            'sem_pii': True,
        },
        'total_eventos': len(events),
        'provedores': dict(sorted(por_provider.items())),
    }


def resetar_telemetry_llm() -> None:
    """Uso exclusivo em testes automatizados."""
    with _lock:
        _telemetry.clear()
    path = _store_path()
    if path.exists():
        path.unlink()
