import logging
from datetime import datetime
from pathlib import Path

import pytest

from app.domain.models import ResultadoMonitoramento
from app.infra.cache import CacheTTL
from app.infra.sqlite_repository import ResultadoRepositorySQLite


@pytest.fixture
def resultado_verde():
    return ResultadoMonitoramento(
        nome="api_teste",
        url="https://exemplo.com",
        status_code=200,
        sucesso=True,
        tempo_resposta_ms=100,
        erro=None,
        consultado_em=datetime.utcnow(),
    )


@pytest.fixture
def repository_tmp(tmp_path: Path):
    return ResultadoRepositorySQLite(tmp_path / "teste.db")


@pytest.fixture
def cache_curto():
    return CacheTTL(ttl_segundos=1)


@pytest.fixture
def logger_teste():
    logger = logging.getLogger("teste_monitorador")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger
