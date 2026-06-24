import logging
from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import ApiAlvo, Configuracao
from app.domain.models import ResultadoMonitoramento
from app.infra.api_client import ApiClient
from app.infra.cache import CacheTTL
from app.infra.sqlite_repository import ResultadoRepositorySQLite
from app.reports.html_report import gerar_relatorio_html
from app.services.monitoramento_service import MonitoramentoService


def criar_resultado(
    *,
    nome: str = "api",
    url: str = "https://example.com",
    status_code: int | None = 200,
    sucesso: bool = True,
    tempo_resposta_ms: float = 100.0,
    erro: str | None = None,
) -> ResultadoMonitoramento:
    return ResultadoMonitoramento(
        nome=nome,
        url=url,
        status_code=status_code,
        sucesso=sucesso,
        tempo_resposta_ms=tempo_resposta_ms,
        erro=erro,
        consultado_em=datetime(2026, 1, 1, 12, 0, 0),
    )


def test_configuracao_padrao_deve_expor_caminhos_e_retries():
    config = Configuracao()

    assert config.banco_sqlite == Path("data/monitoramento.db")
    assert config.diretorio_logs == Path("logs")
    assert config.diretorio_relatorios == Path("reports")
    assert config.tentativas_retry == 3
    assert config.cache_ttl_segundos == 30


def test_api_alvo_deve_usar_timeout_padrao():
    api = ApiAlvo(nome="teste", url="https://example.com")

    assert api.nome == "teste"
    assert api.url == "https://example.com"
    assert api.timeout_segundos == 5.0


def test_status_operacional_deve_classificar_verde_amarelo_vermelho():
    assert criar_resultado(tempo_resposta_ms=999.0).status_operacional == "VERDE"
    assert criar_resultado(tempo_resposta_ms=1500.0).status_operacional == "AMARELO"
    assert criar_resultado(sucesso=False, tempo_resposta_ms=100.0).status_operacional == "VERMELHO"
    assert criar_resultado(tempo_resposta_ms=3000.0).status_operacional == "VERMELHO"


def test_cache_deve_salvar_obter_expirar_e_limpar(monkeypatch):
    tempo = {"valor": 100.0}
    monkeypatch.setattr("app.infra.cache.time.time", lambda: tempo["valor"])

    cache = CacheTTL[str](ttl_segundos=10)
    assert cache.obter("x") is None

    cache.salvar("x", "valor")
    assert cache.obter("x") == "valor"

    tempo["valor"] = 111.0
    assert cache.obter("x") is None

    cache.salvar("y", "valor-2")
    cache.limpar()
    assert cache.obter("y") is None


def test_repository_sqlite_deve_salvar_e_listar(tmp_path):
    repo = ResultadoRepositorySQLite(tmp_path / "monitoramento.db")
    resultado = criar_resultado(nome="api-1", url="https://api.local", tempo_resposta_ms=88.5)

    repo.salvar(resultado)
    registros = repo.listar_ultimos(limite=10)

    assert len(registros) == 1
    assert registros[0]["nome"] == "api-1"
    assert registros[0]["url"] == "https://api.local"
    assert registros[0]["status_operacional"] == "VERDE"


def test_relatorio_html_deve_gerar_arquivo_com_semaforo(tmp_path):
    caminho = tmp_path / "reports" / "dashboard.html"
    resultados = [
        criar_resultado(nome="verde", tempo_resposta_ms=50.0),
        criar_resultado(nome="amarelo", tempo_resposta_ms=1500.0),
        criar_resultado(nome="vermelho", sucesso=False, status_code=500, erro="HTTP 500"),
    ]

    retorno = gerar_relatorio_html(resultados, caminho)

    assert retorno == caminho
    html = caminho.read_text(encoding="utf-8")
    assert "Relatório Monitorador de APIs" in html
    assert "verde" in html
    assert "AMARELO" in html
    assert "HTTP 500" in html


@pytest.mark.asyncio
async def test_service_deve_usar_cache_e_persistir_resultados():
    api = ApiAlvo(nome="api", url="https://api.local")
    resultado = criar_resultado(nome="api", url=api.url)

    class ApiClientFake:
        def __init__(self):
            self.chamadas = 0

        async def consultar(self, api_alvo, tentativas):
            self.chamadas += 1
            assert api_alvo == api
            assert tentativas == 2
            return resultado

    class RepositoryFake:
        def __init__(self):
            self.salvos = []

        def salvar(self, item):
            self.salvos.append(item)

    api_client = ApiClientFake()
    repository = RepositoryFake()
    cache = CacheTTL[ResultadoMonitoramento](ttl_segundos=60)
    logger = logging.getLogger("test-monitorador-service")
    service = MonitoramentoService(api_client, repository, cache, logger, tentativas_retry=2)

    primeira_execucao = await service.executar([api])
    segunda_execucao = await service.executar([api])

    assert primeira_execucao == [resultado]
    assert segunda_execucao == [resultado]
    assert api_client.chamadas == 1
    assert repository.salvos == [resultado, resultado]


@pytest.mark.asyncio
async def test_api_client_deve_retornar_sucesso_com_client_session_mockado(monkeypatch):
    class ResponseFake:
        status = 204

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return "ok"

    class ClientSessionFake:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            assert url == "https://api.local"
            return ResponseFake()

    monkeypatch.setattr("app.infra.api_client.aiohttp.ClientSession", ClientSessionFake)

    resultado = await ApiClient().consultar(
        ApiAlvo(nome="api", url="https://api.local", timeout_segundos=0.01),
        tentativas=1,
        atraso_base=0,
    )

    assert resultado.nome == "api"
    assert resultado.status_code == 204
    assert resultado.sucesso is True
    assert resultado.erro is None
    assert resultado.status_operacional == "VERDE"


@pytest.mark.asyncio
async def test_api_client_deve_retornar_falha_quando_consulta_explodir(monkeypatch):
    async def sleep_fake(_tempo):
        return None

    class ClientSessionFake:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            raise RuntimeError("falha controlada")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.infra.api_client.asyncio.sleep", sleep_fake)
    monkeypatch.setattr("app.infra.api_client.aiohttp.ClientSession", ClientSessionFake)

    resultado = await ApiClient().consultar(
        ApiAlvo(nome="api", url="https://api.local", timeout_segundos=0.01),
        tentativas=1,
        atraso_base=0,
    )

    assert resultado.nome == "api"
    assert resultado.status_code is None
    assert resultado.sucesso is False
    assert "falha controlada" in resultado.erro
