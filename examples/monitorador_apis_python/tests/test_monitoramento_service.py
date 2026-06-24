from unittest.mock import AsyncMock

import pytest

from app.core.config import ApiAlvo
from app.infra.cache import CacheTTL
from app.services.monitoramento_service import MonitoramentoService


@pytest.mark.asyncio
async def test_deve_executar_monitoramento_e_salvar_resultado(
    repository_tmp,
    resultado_verde,
    logger_teste,
):
    api_client = AsyncMock()
    api_client.consultar.return_value = resultado_verde

    service = MonitoramentoService(
        api_client=api_client,
        repository=repository_tmp,
        cache=CacheTTL(ttl_segundos=30),
        logger=logger_teste,
        tentativas_retry=3,
    )

    resultados = await service.executar([
        ApiAlvo(nome="api_teste", url="https://exemplo.com")
    ])

    assert len(resultados) == 1
    assert resultados[0].status_operacional == "VERDE"

    registros = repository_tmp.listar_ultimos()
    assert len(registros) == 1


@pytest.mark.asyncio
async def test_deve_usar_cache_quando_disponivel(
    repository_tmp,
    resultado_verde,
    logger_teste,
):
    api_client = AsyncMock()
    cache = CacheTTL(ttl_segundos=30)
    cache.salvar("https://exemplo.com", resultado_verde)

    service = MonitoramentoService(
        api_client=api_client,
        repository=repository_tmp,
        cache=cache,
        logger=logger_teste,
        tentativas_retry=3,
    )

    resultados = await service.executar([
        ApiAlvo(nome="api_teste", url="https://exemplo.com")
    ])

    assert len(resultados) == 1
    api_client.consultar.assert_not_called()
