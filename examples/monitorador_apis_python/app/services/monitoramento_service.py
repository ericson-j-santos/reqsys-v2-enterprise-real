import asyncio
import logging

from app.core.config import ApiAlvo
from app.domain.models import ResultadoMonitoramento
from app.infra.api_client import ApiClient
from app.infra.cache import CacheTTL
from app.infra.sqlite_repository import ResultadoRepositorySQLite


class MonitoramentoService:
    def __init__(
        self,
        api_client: ApiClient,
        repository: ResultadoRepositorySQLite,
        cache: CacheTTL[ResultadoMonitoramento],
        logger: logging.Logger,
        tentativas_retry: int,
    ):
        self.api_client = api_client
        self.repository = repository
        self.cache = cache
        self.logger = logger
        self.tentativas_retry = tentativas_retry

    async def executar(self, apis: list[ApiAlvo]) -> list[ResultadoMonitoramento]:
        tarefas = [self._consultar_com_cache(api) for api in apis]
        resultados = await asyncio.gather(*tarefas)

        for resultado in resultados:
            self.repository.salvar(resultado)
            self.logger.info(
                "API=%s STATUS=%s HTTP=%s TEMPO_MS=%s ERRO=%s",
                resultado.nome,
                resultado.status_operacional,
                resultado.status_code,
                resultado.tempo_resposta_ms,
                resultado.erro,
            )

        return resultados

    async def _consultar_com_cache(self, api: ApiAlvo) -> ResultadoMonitoramento:
        chave_cache = api.url
        resultado_cache = self.cache.obter(chave_cache)

        if resultado_cache is not None:
            self.logger.info("CACHE_HIT API=%s URL=%s", api.nome, api.url)
            return resultado_cache

        resultado = await self.api_client.consultar(
            api,
            tentativas=self.tentativas_retry,
        )

        self.cache.salvar(chave_cache, resultado)

        return resultado
