import asyncio

import pytest

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry, call_with_retry_async


def _run(coro):
    return asyncio.run(coro)


async def _no_sleep(_seconds):
    return None


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


def test_call_with_retry_async_retorna_no_primeiro_sucesso():
    chamadas = {'n': 0}

    async def fn():
        chamadas['n'] += 1
        return 'ok'

    resultado = _run(call_with_retry_async(fn, max_retries=3, sleep=_no_sleep))

    assert resultado == 'ok'
    assert chamadas['n'] == 1


def test_call_with_retry_async_tenta_novamente_ate_max_retries_e_propaga_erro():
    chamadas = {'n': 0}

    async def fn():
        chamadas['n'] += 1
        raise ValueError('falha transitoria')

    with pytest.raises(ValueError, match='falha transitoria'):
        _run(call_with_retry_async(fn, max_retries=3, retry_on=(ValueError,), sleep=_no_sleep))

    assert chamadas['n'] == 3


def test_call_with_retry_async_circuit_breaker_abre_e_bloqueia():
    circuito = CircuitBreaker(name='teste-async', failure_threshold=2, cooldown_seconds=60)

    async def fn_falha():
        raise ValueError('externo indisponivel')

    for _ in range(2):
        with pytest.raises(ValueError):
            _run(call_with_retry_async(fn_falha, max_retries=1, retry_on=(ValueError,), sleep=_no_sleep, circuit=circuito))

    chamadas = {'n': 0}

    async def fn_nao_deveria_ser_chamada():
        chamadas['n'] += 1
        raise AssertionError('circuito deveria bloquear antes de chamar fn')

    with pytest.raises(CircuitBreakerOpenError, match="Circuito 'teste-async' aberto"):
        _run(call_with_retry_async(fn_nao_deveria_ser_chamada, sleep=_no_sleep, circuit=circuito))

    assert chamadas['n'] == 0
