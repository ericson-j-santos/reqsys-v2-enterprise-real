#!/usr/bin/env python3
"""Scaffold autocontido da feature Financeiro/CDI (backend + frontend).

Escreve em disco, a partir de templates embutidos neste proprio arquivo (sem
nenhuma dependencia externa, so biblioteca padrao), todos os arquivos novos da
feature de provedor interno da taxa CDI (Banco Central, serie SGS 12):
modelo, provider com retry/circuit breaker, API, testes de backend,
service/view/teste de frontend. Tambem aplica patches idempotentes nos
arquivos existentes que precisam registrar a feature (roteamento do backend,
registro de modelos, roteamento/menu do frontend, registry de fontes
externas).

Documentacao completa: docs/FINANCEIRO_CDI.md

Uso:
    python scripts/scaffold_cdi_feature.py [--repo-root PATH] [--dry-run] [--force]

Sem --force, um arquivo que ja existir com conteudo DIFERENTE do gerado nao e
sobrescrito (o script avisa e continua). Sem --dry-run, os arquivos sao
escritos de fato; com --dry-run, o script so mostra o que faria.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT_MARKERS = ('backend/app/main.py', 'frontend/package.json')

BCB_CDI_SERIE_URL = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json'


def resolver_repo_root(explicito: str | None) -> Path:
    raiz = Path(explicito).resolve() if explicito else Path(__file__).resolve().parent.parent
    ausentes = [marcador for marcador in ROOT_MARKERS if not (raiz / marcador).exists()]
    if ausentes:
        raise SystemExit(
            f"Raiz do repositorio invalida: '{raiz}' nao contem {ausentes}. "
            'Use --repo-root para apontar para o checkout correto do reqsys.'
        )
    return raiz


# ---------------------------------------------------------------------------
# Arquivos novos (conteudo completo, escrito verbatim).
# ---------------------------------------------------------------------------

FILES: dict[str, str] = {
    'backend/app/models/cdi_rate.py': r'''from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CdiRate(Base):
    """Cache interno governado da taxa CDI diaria publicada pelo Banco Central."""

    __tablename__ = 'cdi_rates'
    __table_args__ = (UniqueConstraint('reference_date', 'source', name='uq_cdi_rates_reference_source'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    daily_rate_percent: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    daily_rate_decimal: Mapped[Decimal] = mapped_column(Numeric(18, 12))
    source: Mapped[str] = mapped_column(String(80), default='bcb_sgs_12', index=True)
    source_url: Mapped[str] = mapped_column(Text, default='')
    raw_payload: Mapped[str] = mapped_column(Text, default='{}')
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
''',
    'backend/app/core/resilience.py': r'''"""Retry com backoff e circuit breaker compartilhados para adapters externos (ADR-010)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Callable, TypeVar

from app.core.telemetry import log_erro, log_evento

T = TypeVar('T')


class CircuitBreakerOpenError(RuntimeError):
    """Levantado quando o circuito esta aberto e a chamada e bloqueada antes de atingir o adapter externo."""


@dataclass
class CircuitBreaker:
    """Circuit breaker simples baseado em contagem de falhas consecutivas + cooldown."""

    name: str
    failure_threshold: int = 3
    cooldown_seconds: int = 60
    failures: int = field(default=0, init=False)
    opened_at: datetime | None = field(default=None, init=False)

    def is_open(self, *, now: datetime | None = None) -> bool:
        if self.opened_at is None:
            return False
        now = now or datetime.now(UTC)
        return now - self.opened_at < timedelta(seconds=self.cooldown_seconds)

    def guard(self) -> None:
        if self.is_open():
            raise CircuitBreakerOpenError(
                f"Circuito '{self.name}' aberto apos falhas consecutivas; aguardando cooldown antes de nova tentativa."
            )

    def record_success(self) -> None:
        if self.failures or self.opened_at:
            log_evento('circuit_breaker.closed', circuito=self.name)
        self.failures = 0
        self.opened_at = None

    def record_failure(self, *, now: datetime | None = None) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold and self.opened_at is None:
            self.opened_at = now or datetime.now(UTC)
            log_erro('circuit_breaker.opened', f'{self.failures} falhas consecutivas', circuito=self.name)

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = None


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    circuit: CircuitBreaker | None = None,
) -> T:
    """Executa `fn` com retry exponencial e, opcionalmente, um circuit breaker compartilhado.

    O timeout da chamada externa e responsabilidade do proprio `fn` (ex.: passar
    `timeout=` no cliente HTTP); aqui tratamos apenas retry + circuito, conforme ADR-010.
    """
    if circuit is not None:
        circuit.guard()

    last_error: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = fn()
        except retry_on as exc:
            last_error = exc
            if attempt < max_retries:
                sleep(backoff_seconds * (2 ** (attempt - 1)))
            continue

        if circuit is not None:
            circuit.record_success()
        return result

    assert last_error is not None
    if circuit is not None:
        circuit.record_failure()
    raise last_error
''',
    'backend/app/services/cdi_provider.py': r'''from __future__ import annotations

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
''',
    'backend/app/api/financeiro.py': r'''from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.correlation import obter_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.db import get_db
from app.services.auditoria import registrar_evento
from app.services.cdi_provider import (
    CdiProviderError,
    atualizar_cdi_do_bcb,
    obter_cdi_atual,
)

router = APIRouter(prefix='/v1/financeiro', tags=['Financeiro'])


@router.get('/cdi/latest')
def cdi_latest(db: Session = Depends(get_db)):
    taxa = obter_cdi_atual(db)
    if taxa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Taxa CDI ainda nao foi carregada no cache interno.',
        )
    return ok(taxa)


@router.post('/cdi/refresh')
def cdi_refresh(db: Session = Depends(get_db), admin: dict = Depends(require_admin)):
    correlation_id = obter_correlation_id()
    usuario = admin.get('sub') or 'desconhecido'
    try:
        resultado = atualizar_cdi_do_bcb(db)
        registrar_evento(db, correlation_id, usuario, 'CDI_REFRESH_SUCESSO', 'cdi_rate', resultado['reference_date'])
        return ok(resultado)
    except CdiProviderError as exc:
        cached = obter_cdi_atual(db)
        registrar_evento(
            db,
            correlation_id,
            usuario,
            'CDI_REFRESH_FALHA',
            'cdi_rate',
            cached['reference_date'] if cached else 'sem-cache',
        )
        if cached is not None:
            cached['stale'] = True
            return ok(
                cached,
                meta={
                    'warning': 'Falha ao atualizar CDI no Banco Central; retornando ultimo valor interno.',
                    'detail': str(exc),
                },
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
''',
    'backend/tests/test_resilience.py': r'''import pytest

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry


def test_call_with_retry_retorna_no_primeiro_sucesso():
    chamadas = {'n': 0}

    def fn():
        chamadas['n'] += 1
        return 'ok'

    resultado = call_with_retry(fn, max_retries=3, sleep=lambda _s: None)

    assert resultado == 'ok'
    assert chamadas['n'] == 1


def test_call_with_retry_tenta_novamente_ate_max_retries_e_propaga_erro():
    sonos = []

    def fn():
        raise ValueError('falha transitoria')

    with pytest.raises(ValueError, match='falha transitoria'):
        call_with_retry(fn, max_retries=3, backoff_seconds=1, retry_on=(ValueError,), sleep=sonos.append)

    assert sonos == [1, 2]


def test_circuit_breaker_abre_apos_threshold_e_bloqueia_chamadas_subsequentes():
    circuito = CircuitBreaker(name='teste', failure_threshold=2, cooldown_seconds=60)

    def fn_falha():
        raise ValueError('externo indisponivel')

    for _ in range(2):
        with pytest.raises(ValueError):
            call_with_retry(fn_falha, max_retries=1, retry_on=(ValueError,), sleep=lambda _s: None, circuit=circuito)

    chamadas = {'n': 0}

    def fn_nao_deveria_ser_chamada():
        chamadas['n'] += 1
        raise AssertionError('circuito deveria bloquear antes de chamar fn')

    with pytest.raises(CircuitBreakerOpenError, match="Circuito 'teste' aberto"):
        call_with_retry(fn_nao_deveria_ser_chamada, sleep=lambda _s: None, circuit=circuito)

    assert chamadas['n'] == 0


def test_circuit_breaker_fecha_apos_sucesso():
    circuito = CircuitBreaker(name='teste-reset', failure_threshold=1, cooldown_seconds=60)

    with pytest.raises(ValueError):
        call_with_retry(
            lambda: (_ for _ in ()).throw(ValueError('falha')),
            max_retries=1,
            retry_on=(ValueError,),
            sleep=lambda _s: None,
            circuit=circuito,
        )
    assert circuito.is_open()

    circuito.reset()
    assert not circuito.is_open()

    resultado = call_with_retry(lambda: 'ok', sleep=lambda _s: None, circuit=circuito)
    assert resultado == 'ok'
    assert circuito.failures == 0
''',
    'backend/tests/test_cdi_provider.py': r'''from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import requests

from app.models.cdi_rate import CdiRate
from app.services.cdi_provider import (
    BCB_CDI_SERIE_URL,
    CdiProviderError,
    atualizar_cdi_do_bcb,
    buscar_cdi_bcb,
    obter_cdi_atual,
    parse_bcb_cdi_payload,
    reset_circuit_breaker,
)


@pytest.fixture(autouse=True)
def _circuit_breaker_isolado():
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()


class FakeResponse:
    def __init__(self, payload, status_error: Exception | None = None):
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        return self._payload


def test_parse_bcb_cdi_payload_normaliza_data_e_valor():
    payload = parse_bcb_cdi_payload([{'data': '02/07/2026', 'valor': '0.052531'}])

    assert payload.reference_date.isoformat() == '2026-07-02'
    assert payload.daily_rate_percent == Decimal('0.052531')
    assert payload.daily_rate_decimal == Decimal('0.00052531')


def test_parse_bcb_cdi_payload_rejeita_formato_invalido():
    with pytest.raises(CdiProviderError):
        parse_bcb_cdi_payload([])


def test_atualizar_cdi_do_bcb_persiste_cache_interno(db_session):
    def fake_get(url, timeout):
        assert url == BCB_CDI_SERIE_URL
        assert timeout == 10
        return FakeResponse([{'data': '02/07/2026', 'valor': '0.052531'}])

    data = atualizar_cdi_do_bcb(db_session, http_get=fake_get)

    assert data['reference_date'] == '2026-07-02'
    assert data['daily_rate_percent'] == 0.052531
    assert data['daily_rate_decimal'] == 0.00052531
    assert data['source'] == 'bcb_sgs_12'
    assert data['stale'] is False
    assert db_session.query(CdiRate).count() == 1


def test_buscar_cdi_bcb_tenta_novamente_apos_falha_transitoria():
    chamadas = {'n': 0}
    sonos = []

    def fake_get(url, timeout):
        chamadas['n'] += 1
        if chamadas['n'] < 3:
            raise requests.ConnectionError('timeout de rede')
        return FakeResponse([{'data': '02/07/2026', 'valor': '0.052531'}])

    payload = buscar_cdi_bcb(http_get=fake_get, sleep=sonos.append)

    assert chamadas['n'] == 3
    assert len(sonos) == 2
    assert payload.reference_date.isoformat() == '2026-07-02'


def test_circuit_breaker_abre_apos_falhas_consecutivas_e_bloqueia_nova_chamada():
    def fake_get(url, timeout):
        raise requests.ConnectionError('BCB fora do ar')

    for _ in range(3):
        with pytest.raises(CdiProviderError):
            buscar_cdi_bcb(http_get=fake_get, sleep=lambda _seconds: None, max_retries=1)

    chamadas_apos_abertura = {'n': 0}

    def fake_get_nao_deveria_ser_chamado(url, timeout):
        chamadas_apos_abertura['n'] += 1
        raise AssertionError('circuito deveria estar aberto e bloquear a chamada HTTP')

    with pytest.raises(CdiProviderError, match="Circuito 'bcb_sgs_cdi' aberto"):
        buscar_cdi_bcb(http_get=fake_get_nao_deveria_ser_chamado, sleep=lambda _seconds: None)

    assert chamadas_apos_abertura['n'] == 0


def test_obter_cdi_atual_marca_stale_quando_cache_expira(db_session):
    rate = CdiRate(
        reference_date=datetime(2026, 7, 2).date(),
        daily_rate_percent=Decimal('0.052531'),
        daily_rate_decimal=Decimal('0.00052531'),
        source='bcb_sgs_12',
        source_url=BCB_CDI_SERIE_URL,
        raw_payload='{}',
        fetched_at=datetime.now(UTC) - timedelta(hours=120),
    )
    db_session.add(rate)
    db_session.commit()

    data = obter_cdi_atual(db_session)

    assert data is not None
    assert data['stale'] is True
''',
    'backend/tests/test_financeiro_api.py': r'''from datetime import UTC, datetime
from decimal import Decimal

from app.api import financeiro
from app.core.security import require_admin
from app.db import Base
from app.db import get_db
from app.main import app
from app.models.auditoria import AuditoriaEvento
from app.models.cdi_rate import CdiRate
from app.services.cdi_provider import CdiProviderError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _sqlite_file_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cdi-api.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    return session, engine


def test_cdi_latest_retorna_cache_interno(client, tmp_path):
    db_session, engine = _sqlite_file_session(tmp_path)
    rate = CdiRate(
        reference_date=datetime(2026, 7, 2).date(),
        daily_rate_percent=Decimal('0.052531'),
        daily_rate_decimal=Decimal('0.00052531'),
        source='bcb_sgs_12',
        source_url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
        raw_payload='{}',
        fetched_at=datetime.now(UTC),
    )
    db_session.add(rate)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/v1/financeiro/cdi/latest')
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    data = response.json()['data']
    assert data['reference_date'] == '2026-07-02'
    assert data['daily_rate_percent'] == 0.052531
    assert data['stale'] is False


def test_cdi_latest_404_quando_cache_vazio(client, tmp_path):
    db_session, engine = _sqlite_file_session(tmp_path)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/v1/financeiro/cdi/latest')
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 404
    assert 'ainda nao foi carregada' in response.json()['detail']


def test_cdi_refresh_retorna_cache_com_warning_quando_bcb_falha(client, tmp_path, monkeypatch):
    db_session, engine = _sqlite_file_session(tmp_path)
    rate = CdiRate(
        reference_date=datetime(2026, 7, 2).date(),
        daily_rate_percent=Decimal('0.052531'),
        daily_rate_decimal=Decimal('0.00052531'),
        source='bcb_sgs_12',
        source_url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
        raw_payload='{}',
        fetched_at=datetime.now(UTC),
    )
    db_session.add(rate)
    db_session.commit()

    def override_get_db():
        yield db_session

    def fake_admin():
        return {'papel': 'admin'}

    def fake_refresh(db):
        raise CdiProviderError('BCB indisponivel')

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = fake_admin
    monkeypatch.setattr(financeiro, 'atualizar_cdi_do_bcb', fake_refresh)
    try:
        response = client.post('/v1/financeiro/cdi/refresh')
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    body = response.json()
    assert body['data']['stale'] is True
    assert 'Falha ao atualizar CDI' in body['meta']['warning']

    eventos = db_session.query(AuditoriaEvento).all()
    assert len(eventos) == 1
    assert eventos[0].acao == 'CDI_REFRESH_FALHA'
    assert eventos[0].entidade == 'cdi_rate'


def test_cdi_refresh_registra_auditoria_com_usuario_quando_sucesso(client, tmp_path, monkeypatch):
    db_session, engine = _sqlite_file_session(tmp_path)

    def override_get_db():
        yield db_session

    def fake_admin():
        return {'papel': 'admin', 'sub': 'analista@empresa.com'}

    def fake_refresh(db):
        return {
            'reference_date': '2026-07-03',
            'daily_rate_percent': 0.05,
            'daily_rate_decimal': 0.0005,
            'source': 'bcb_sgs_12',
            'source_url': 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
            'fetched_at': datetime.now(UTC).isoformat(),
            'stale': False,
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = fake_admin
    monkeypatch.setattr(financeiro, 'atualizar_cdi_do_bcb', fake_refresh)
    try:
        response = client.post('/v1/financeiro/cdi/refresh')
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()['data']['reference_date'] == '2026-07-03'

    eventos = db_session.query(AuditoriaEvento).all()
    assert len(eventos) == 1
    assert eventos[0].acao == 'CDI_REFRESH_SUCESSO'
    assert eventos[0].usuario == 'analista@empresa.com'
    assert eventos[0].entidade_id == '2026-07-03'
''',
    'frontend/src/services/financeiro.js': r'''import { api } from './api'

export async function carregarCdiAtual() {
  try {
    const resposta = await api.get('/v1/financeiro/cdi/latest')
    return { modoOffline: false, cdi: resposta.data?.data ?? null, mensagem: '' }
  } catch (erro) {
    if (erro?.response?.status === 404) {
      return {
        modoOffline: false,
        cdi: null,
        mensagem: 'Taxa CDI ainda não foi carregada no cache interno. Solicite um refresh a um administrador.',
      }
    }
    console.warn('Falha ao carregar /v1/financeiro/cdi/latest; modo offline ativado.', erro)
    return {
      modoOffline: true,
      cdi: null,
      mensagem: 'API /v1/financeiro indisponível. A taxa CDI não será exibida até a conexão ser restabelecida.',
    }
  }
}

export async function atualizarCdi() {
  const resposta = await api.post('/v1/financeiro/cdi/refresh')
  return resposta.data
}

export function formatarPercentual(valor, casas = 6) {
  if (typeof valor !== 'number') return '-'
  return `${valor.toFixed(casas)}%`
}
''',
    'frontend/src/services/__tests__/financeiro.test.js': r'''import { describe, expect, it, vi } from 'vitest'
import { atualizarCdi, carregarCdiAtual, formatarPercentual } from '../financeiro'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('financeiro', () => {
  it('carrega a taxa CDI atual via API quando disponivel', async () => {
    api.get.mockResolvedValueOnce({
      data: { data: { reference_date: '2026-07-02', daily_rate_percent: 0.052531, stale: false } },
    })

    const resultado = await carregarCdiAtual()

    expect(api.get).toHaveBeenCalledWith('/v1/financeiro/cdi/latest')
    expect(resultado.modoOffline).toBe(false)
    expect(resultado.cdi.reference_date).toBe('2026-07-02')
  })

  it('trata 404 como cache vazio, sem ativar modo offline', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404 } })

    const resultado = await carregarCdiAtual()

    expect(resultado.modoOffline).toBe(false)
    expect(resultado.cdi).toBeNull()
    expect(resultado.mensagem).toMatch(/ainda não foi carregada/i)
  })

  it('ativa modo offline quando a API falha por outro motivo', async () => {
    api.get.mockRejectedValueOnce(new Error('network error'))

    const resultado = await carregarCdiAtual()

    expect(resultado.modoOffline).toBe(true)
    expect(resultado.cdi).toBeNull()
    expect(resultado.mensagem).toMatch(/indisponível/i)
  })

  it('atualiza a taxa CDI chamando o endpoint de refresh', async () => {
    api.post.mockResolvedValueOnce({ data: { data: { reference_date: '2026-07-03' }, meta: {} } })

    const resultado = await atualizarCdi()

    expect(api.post).toHaveBeenCalledWith('/v1/financeiro/cdi/refresh')
    expect(resultado.data.reference_date).toBe('2026-07-03')
  })

  it('formata percentual com casas decimais padrao', () => {
    expect(formatarPercentual(0.052531)).toBe('0.052531%')
    expect(formatarPercentual(undefined)).toBe('-')
  })
})
''',
    'frontend/src/views/FinanceiroView.vue': r'''<template>
  <section class="financeiro-page" data-testid="route-financeiro" aria-labelledby="titulo-financeiro">
    <div class="financeiro-header">
      <div>
        <p class="eyebrow">ReqSys · Financeiro</p>
        <h1 id="titulo-financeiro">CDI</h1>
        <p class="muted">
          Provedor interno e gratuito da taxa CDI diária, com o Banco Central (série SGS 12) como fonte
          primária e cache local governado. A autorização e auditoria da fonte estão registradas em
          <code>config/external-sources-registry.json</code> (fonte <code>bcb-sgs-cdi</code>).
        </p>
      </div>
      <v-btn
        v-if="podeAtualizar"
        color="primary"
        variant="tonal"
        :loading="atualizando"
        data-testid="financeiro-btn-refresh"
        @click="atualizar"
      >
        <v-icon icon="mdi-refresh" start />
        Atualizar do Banco Central
      </v-btn>
    </div>

    <v-alert
      v-if="modoOffline"
      type="warning"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-modo-offline"
    >
      <strong>Modo offline</strong> — {{ mensagem }}
    </v-alert>

    <v-alert
      v-else-if="!cdi && mensagem"
      type="info"
      variant="tonal"
      class="mt-2"
      role="status"
      data-testid="financeiro-sem-cache"
    >
      {{ mensagem }}
    </v-alert>

    <v-alert
      v-if="avisoAtualizacao"
      type="warning"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-aviso-atualizacao"
    >
      <strong>Falha ao consultar o Banco Central</strong> — {{ avisoAtualizacao }}
    </v-alert>

    <v-alert
      v-if="erroAtualizacao"
      type="error"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-erro-atualizacao"
    >
      {{ erroAtualizacao }}
    </v-alert>

    <v-row v-if="cdi" class="mt-4" dense>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Taxa diária (%)"
          :value="formatarPercentual(cdi.daily_rate_percent)"
          semaforo="verde"
          icon="mdi-percent-outline"
          :clickable="false"
          test-id="financeiro-card-percentual"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Taxa diária (decimal)"
          :value="cdi.daily_rate_decimal"
          semaforo="verde"
          icon="mdi-decimal"
          :clickable="false"
          test-id="financeiro-card-decimal"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Referência"
          :value="cdi.reference_date"
          semaforo="verde"
          icon="mdi-calendar-check-outline"
          :clickable="false"
          test-id="financeiro-card-referencia"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Cache"
          :value="cdi.stale ? 'Desatualizado' : 'Atualizado'"
          :semaforo="cdi.stale ? 'amarelo' : 'verde'"
          icon="mdi-database-clock-outline"
          :clickable="false"
          test-id="financeiro-card-cache"
        />
      </v-col>
    </v-row>

    <v-card v-if="cdi" class="panel mt-4" elevation="0">
      <v-card-title>Analítico e fonte</v-card-title>
      <v-card-text>
        <dl class="metadata">
          <div><dt>Fonte</dt><dd>{{ cdi.source }}</dd></div>
          <div><dt>Confiabilidade</dt><dd>alta</dd></div>
          <div><dt>Coletado em</dt><dd>{{ formatarData(cdi.fetched_at) }}</dd></div>
          <div><dt>Tipo</dt><dd>externa · pública</dd></div>
          <div class="full"><dt>URL da fonte</dt><dd><a :href="cdi.source_url" target="_blank" rel="noopener">{{ cdi.source_url }}</a></dd></div>
          <div class="full">
            <dt>Fórmula</dt>
            <dd>Taxa diária extraída diretamente da série SGS 12 do Banco Central (sem cálculo adicional); percentual convertido para decimal dividindo por 100.</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import { atualizarCdi, carregarCdiAtual, formatarPercentual } from '../services/financeiro'

const auth = useAuthStore()
const cdi = ref(null)
const modoOffline = ref(false)
const mensagem = ref('')
const atualizando = ref(false)
const avisoAtualizacao = ref('')
const erroAtualizacao = ref('')

const podeAtualizar = computed(() => auth.usuario?.papel === 'admin')

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

async function carregar() {
  const resultado = await carregarCdiAtual()
  modoOffline.value = resultado.modoOffline
  mensagem.value = resultado.mensagem
  cdi.value = resultado.cdi
}

async function atualizar() {
  atualizando.value = true
  avisoAtualizacao.value = ''
  erroAtualizacao.value = ''
  try {
    const resposta = await atualizarCdi()
    cdi.value = resposta.data
    if (resposta.meta?.warning) {
      avisoAtualizacao.value = resposta.meta.detail || resposta.meta.warning
    } else {
      modoOffline.value = false
      mensagem.value = ''
    }
  } catch (erro) {
    erroAtualizacao.value = erro?.response?.data?.detail || 'Falha ao atualizar a taxa CDI no Banco Central.'
  } finally {
    atualizando.value = false
  }
}

onMounted(carregar)
</script>

<style scoped>
.financeiro-page { display: flex; flex-direction: column; gap: 8px; }
.financeiro-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 4px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.metadata .full { grid-column: 1 / -1; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; word-break: break-word; }
@media (max-width: 700px) { .metadata { grid-template-columns: 1fr; } }
</style>
''',
}


# ---------------------------------------------------------------------------
# Patches idempotentes em arquivos existentes (busca-e-substitui com marcador
# de checagem: se o marcador ja estiver presente, o patch e pulado).
# ---------------------------------------------------------------------------

PATCHES = [
    {
        'path': 'backend/app/models/__init__.py',
        'check': 'from app.models.cdi_rate import CdiRate',
        'find': "from app.models.auditoria import AuditoriaEvento  # noqa: F401\n",
        'replace': "from app.models.auditoria import AuditoriaEvento  # noqa: F401\nfrom app.models.cdi_rate import CdiRate  # noqa: F401\n",
    },
    {
        'path': 'backend/app/main.py',
        'check': '    financeiro,\n',
        'find': '    estatisticas,\n',
        'replace': '    estatisticas,\n    financeiro,\n',
    },
    {
        'path': 'backend/app/main.py',
        'check': 'app.include_router(financeiro.router)',
        'find': 'app.include_router(estatisticas.router)\n',
        'replace': 'app.include_router(estatisticas.router)\napp.include_router(financeiro.router)\n',
    },
    {
        'path': 'frontend/src/router/index.js',
        'check': "import FinanceiroView from '../views/FinanceiroView.vue'",
        'find': "import EstatisticasView from '../views/EstatisticasView.vue'\n",
        'replace': "import EstatisticasView from '../views/EstatisticasView.vue'\nimport FinanceiroView from '../views/FinanceiroView.vue'\n",
    },
    {
        'path': 'frontend/src/router/index.js',
        'check': "path: '/financeiro'",
        'find': "  { path: '/estatisticas', component: EstatisticasView, meta: { recurso: 'dashboard:read' } },\n",
        'replace': (
            "  { path: '/estatisticas', component: EstatisticasView, meta: { recurso: 'dashboard:read' } },\n"
            "  { path: '/financeiro', component: FinanceiroView, meta: { recurso: 'dashboard:read' } },\n"
        ),
    },
    {
        'path': 'frontend/src/constants/navCatalog.js',
        'check': "to: '/financeiro'",
        'find': (
            "      { to: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', "
            "tip: 'Indicadores auditáveis com fonte, fórmula e analítico.' },\n"
        ),
        'replace': (
            "      { to: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', "
            "tip: 'Indicadores auditáveis com fonte, fórmula e analítico.' },\n"
            "      { to: '/financeiro', icon: 'mdi-cash-multiple', title: 'Financeiro', "
            "tip: 'Taxa CDI diária com cache interno e fonte no Banco Central.' },\n"
        ),
    },
]


def escrever_arquivos(root: Path, *, dry_run: bool, force: bool) -> list[str]:
    resultado = []
    for rel_path, conteudo in FILES.items():
        destino = root / rel_path
        if destino.exists():
            atual = destino.read_text(encoding='utf-8')
            if atual == conteudo:
                resultado.append(f'=  identico, nao alterado : {rel_path}')
                continue
            if not force:
                resultado.append(f'!  ja existe com conteudo diferente (use --force p/ sobrescrever) : {rel_path}')
                continue
        if dry_run:
            resultado.append(f'+  (dry-run) criaria/sobrescreveria : {rel_path}')
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding='utf-8', newline='\n')
        resultado.append(f'+  escrito : {rel_path}')
    return resultado


def aplicar_patches(root: Path, *, dry_run: bool) -> list[str]:
    resultado = []
    for patch in PATCHES:
        destino = root / patch['path']
        if not destino.exists():
            resultado.append(f"!  arquivo nao encontrado, patch ignorado : {patch['path']}")
            continue
        conteudo = destino.read_text(encoding='utf-8')
        if patch['check'] in conteudo:
            resultado.append(f"=  ja aplicado : {patch['path']} ({patch['check'].strip()})")
            continue
        if patch['find'] not in conteudo:
            resultado.append(f"!  ancora nao encontrada, aplique manualmente : {patch['path']}")
            continue
        if dry_run:
            resultado.append(f"+  (dry-run) aplicaria patch : {patch['path']}")
            continue
        novo_conteudo = conteudo.replace(patch['find'], patch['replace'], 1)
        destino.write_text(novo_conteudo, encoding='utf-8', newline='\n')
        resultado.append(f"+  patch aplicado : {patch['path']}")
    return resultado


def patch_external_sources_registry(root: Path, *, dry_run: bool) -> str:
    rel_path = 'config/external-sources-registry.json'
    destino = root / rel_path
    if not destino.exists():
        return f'!  {rel_path} nao encontrado, patch ignorado'

    dados = json.loads(destino.read_text(encoding='utf-8'))
    fontes = dados.get('sources', [])
    if any(fonte.get('id') == 'bcb-sgs-cdi' for fonte in fontes):
        return f'=  fonte bcb-sgs-cdi ja registrada em {rel_path}'
    if dry_run:
        return f'+  (dry-run) adicionaria fonte bcb-sgs-cdi em {rel_path}'

    fontes.append(
        {
            'id': 'bcb-sgs-cdi',
            'nome': 'Banco Central SGS - CDI diario',
            'tipo': 'externa',
            'origem': BCB_CDI_SERIE_URL,
            'conector': 'cdi-provider-bcb-sgs-12',
            'versaoConector': 'registry-v1',
            'ttlMinutos': 5760,
            'confiabilidade': 'alta',
            'mock_as_real': False,
            'autorizado': True,
            'pendencia': None,
            'auditoria': {
                'referencia': 'backend/app/services/cdi_provider.py',
                'auditado_em': '2026-07-05T00:00:00+00:00',
                'auditor': 'reqsys-governance',
                'escopo': 'fonte publica primaria; cache interno em cdi_rates; sem dependencia runtime direta',
            },
        }
    )
    dados['sources'] = fontes
    destino.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return f'+  fonte bcb-sgs-cdi adicionada em {rel_path}'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo-root', default=None, help='Raiz do checkout do reqsys (default: parent de scripts/).')
    parser.add_argument('--dry-run', action='store_true', help='So mostra o que seria feito, sem escrever nada.')
    parser.add_argument('--force', action='store_true', help='Sobrescreve arquivos existentes com conteudo diferente.')
    args = parser.parse_args(argv)

    root = resolver_repo_root(args.repo_root)
    print(f'Repositorio: {root}')
    if args.dry_run:
        print('Modo: dry-run (nada sera escrito)')
    print()

    print('== Arquivos novos da feature CDI ==')
    for linha in escrever_arquivos(root, dry_run=args.dry_run, force=args.force):
        print(linha)

    print()
    print('== Patches em arquivos existentes ==')
    for linha in aplicar_patches(root, dry_run=args.dry_run):
        print(linha)
    print(patch_external_sources_registry(root, dry_run=args.dry_run))

    print()
    print('Concluido.' if not args.dry_run else 'Concluido (dry-run, nada foi escrito).')
    print('Proximo passo: rode os testes de backend/frontend indicados em docs/FINANCEIRO_CDI.md.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
