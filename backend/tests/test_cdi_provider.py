from datetime import UTC, datetime, timedelta
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
