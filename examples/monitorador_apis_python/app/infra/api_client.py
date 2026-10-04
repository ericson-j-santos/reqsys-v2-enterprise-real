import asyncio
import time
from datetime import datetime

import aiohttp

from app.core.config import ApiAlvo
from app.domain.models import ResultadoMonitoramento


class ApiClient:
    async def consultar(
        self,
        api: ApiAlvo,
        tentativas: int = 3,
        atraso_base: float = 0.5,
    ) -> ResultadoMonitoramento:
        ultimo_erro: str | None = None
        inicio = time.perf_counter()

        for tentativa in range(1, tentativas + 1):
            inicio = time.perf_counter()

            try:
                timeout = aiohttp.ClientTimeout(total=api.timeout_segundos)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(api.url) as response:
                        await response.text()
                        tempo_ms = (time.perf_counter() - inicio) * 1000
                        sucesso = 200 <= response.status < 300

                        return ResultadoMonitoramento(
                            nome=api.nome,
                            url=api.url,
                            status_code=response.status,
                            sucesso=sucesso,
                            tempo_resposta_ms=round(tempo_ms, 2),
                            erro=None if sucesso else f"HTTP {response.status}",
                            consultado_em=datetime.utcnow(),
                        )

            except Exception as erro:
                ultimo_erro = str(erro)
                if tentativa < tentativas:
                    await asyncio.sleep(atraso_base * tentativa)

        tempo_ms = (time.perf_counter() - inicio) * 1000

        return ResultadoMonitoramento(
            nome=api.nome,
            url=api.url,
            status_code=None,
            sucesso=False,
            tempo_resposta_ms=round(tempo_ms, 2),
            erro=ultimo_erro or "Erro desconhecido",
            consultado_em=datetime.utcnow(),
        )
