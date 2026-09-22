import asyncio

from app.core.config import APIS_PADRAO, Configuracao
from app.core.logger import configurar_logger
from app.infra.api_client import ApiClient
from app.infra.cache import CacheTTL
from app.infra.sqlite_repository import ResultadoRepositorySQLite
from app.reports.html_report import gerar_relatorio_html
from app.services.monitoramento_service import MonitoramentoService


async def main() -> None:
    config = Configuracao()

    logger = configurar_logger(config.diretorio_logs)
    repository = ResultadoRepositorySQLite(config.banco_sqlite)
    cache = CacheTTL(ttl_segundos=config.cache_ttl_segundos)
    api_client = ApiClient()

    service = MonitoramentoService(
        api_client=api_client,
        repository=repository,
        cache=cache,
        logger=logger,
        tentativas_retry=config.tentativas_retry,
    )

    resultados = await service.executar(APIS_PADRAO)

    caminho_relatorio = gerar_relatorio_html(
        resultados=resultados,
        caminho_saida=config.diretorio_relatorios / "relatorio_monitoramento.html",
    )

    logger.info("RELATORIO_GERADO caminho=%s", caminho_relatorio)
    print(f"Relatório gerado em: {caminho_relatorio}")


if __name__ == "__main__":
    asyncio.run(main())
