from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import requests
from sqlalchemy.orm import Session

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry
from app.models.cdi_rate import CdiRate

BCB_CDI_SOURCE = 'bcb_sgs_12'
BCB_CDI_SERIE_URL = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json'
DEFAULT_STALE_AFTER_HOURS = 96

BCB_MAX_RETRIES = 3
BCB_RETRY_BACKOFF_SECONDS = 0.5
BCB_CIRCUIT_FAILURE_THRESHOLD = 3
BCB_CIRCUIT_COOLDOWN_SECONDS = 60

_bcb_circuit = CircuitBreaker(
    name='bcb_sgs_cdi',
    failure_threshold=BCB_CIRCUIT_FAILURE_THRESHOLD,
    cooldown_seconds=BCB_CIRCUIT_COOLDOWN_SECONDS,
)


class CdiProviderError(RuntimeError):
    """Erro controlado na ingestao da taxa CDI."""


def reset_circuit_breaker() -> None:
    """Reseta o estado do circuit breaker (uso em testes)."""
    _bcb_circuit.reset()


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


@dataclass(frozen=True)
class CdiRatePayload:
    reference_date: date
    daily_rate_percent: Decimal
    daily_rate_decimal: Decimal
    raw_payload: dict[str, Any]


def _parse_reference_date(value: str) -> date:
    try:
        return datetime.strptime(value, '%d/%m/%Y').date()
    except ValueError as exc:
        raise CdiProviderError(f'Data CDI invalida recebida do BCB: {value!r}') from exc


def _parse_decimal(value: str) -> Decimal:
    normalized = str(value).strip().replace(',', '.')
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise CdiProviderError(f'Valor CDI invalido recebido do BCB: {value!r}') from exc


def parse_bcb_cdi_payload(payload: Any) -> CdiRatePayload:
    if not isinstance(payload, list) or not payload:
        raise CdiProviderError('Payload CDI do BCB vazio ou em formato inesperado.')

    item = payload[0]
    if not isinstance(item, dict):
        raise CdiProviderError('Item CDI do BCB em formato inesperado.')

    reference_date = _parse_reference_date(str(item.get('data') or ''))
    daily_rate_percent = _parse_decimal(str(item.get('valor') or ''))
    daily_rate_decimal = daily_rate_percent / Decimal('100')
    return CdiRatePayload(
        reference_date=reference_date,
        daily_rate_percent=daily_rate_percent,
        daily_rate_decimal=daily_rate_decimal,
        raw_payload=item,
    )


def _serialize_rate(rate: CdiRate, *, stale: bool = False) -> dict[str, Any]:
    return {
        'reference_date': rate.reference_date.isoformat(),
        'daily_rate_percent': float(rate.daily_rate_percent),
        'daily_rate_decimal': float(rate.daily_rate_decimal),
        'source': rate.source,
        'source_url': rate.source_url,
        'fetched_at': _as_utc(rate.fetched_at).isoformat(),
        'stale': stale,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fetch_bcb_payload(http_get) -> Any:
    try:
        response: HttpResponse = http_get(BCB_CDI_SERIE_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise CdiProviderError(f'Falha ao consultar CDI no Banco Central: {exc}') from exc
    except ValueError as exc:
        raise CdiProviderError('Resposta CDI do Banco Central nao e JSON valido.') from exc


def buscar_cdi_bcb(http_get=requests.get, *, sleep=time.sleep, max_retries: int = BCB_MAX_RETRIES) -> CdiRatePayload:
    try:
        payload = call_with_retry(
            lambda: _fetch_bcb_payload(http_get),
            max_retries=max_retries,
            backoff_seconds=BCB_RETRY_BACKOFF_SECONDS,
            retry_on=(CdiProviderError,),
            sleep=sleep,
            circuit=_bcb_circuit,
        )
    except CircuitBreakerOpenError as exc:
        raise CdiProviderError(str(exc)) from exc

    return parse_bcb_cdi_payload(payload)


def salvar_cdi_rate(db: Session, payload: CdiRatePayload, *, fetched_at: datetime | None = None) -> CdiRate:
    fetched_at = fetched_at or datetime.now(UTC)
    rate = (
        db.query(CdiRate)
        .filter(CdiRate.reference_date == payload.reference_date, CdiRate.source == BCB_CDI_SOURCE)
        .one_or_none()
    )
    if rate is None:
        rate = CdiRate(
            reference_date=payload.reference_date,
            source=BCB_CDI_SOURCE,
            source_url=BCB_CDI_SERIE_URL,
            fetched_at=fetched_at,
        )
        db.add(rate)

    rate.daily_rate_percent = payload.daily_rate_percent
    rate.daily_rate_decimal = payload.daily_rate_decimal
    rate.raw_payload = json.dumps(payload.raw_payload, ensure_ascii=False, sort_keys=True)
    rate.fetched_at = fetched_at
    db.commit()
    db.refresh(rate)
    return rate


def atualizar_cdi_do_bcb(db: Session, http_get=requests.get) -> dict[str, Any]:
    payload = buscar_cdi_bcb(http_get=http_get)
    rate = salvar_cdi_rate(db, payload)
    return _serialize_rate(rate, stale=False)


def obter_ultimo_cdi(db: Session) -> CdiRate | None:
    return db.query(CdiRate).order_by(CdiRate.reference_date.desc(), CdiRate.id.desc()).first()


def obter_cdi_atual(db: Session, *, stale_after_hours: int = DEFAULT_STALE_AFTER_HOURS) -> dict[str, Any] | None:
    rate = obter_ultimo_cdi(db)
    if rate is None:
        return None

    stale_limit = datetime.now(UTC) - timedelta(hours=stale_after_hours)
    stale = _as_utc(rate.fetched_at) < stale_limit
    return _serialize_rate(rate, stale=stale)
