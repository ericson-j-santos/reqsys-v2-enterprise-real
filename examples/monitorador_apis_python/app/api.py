from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse

from app.core.config import APIS_PADRAO, Configuracao
from app.core.logger import configurar_logger
from app.infra.api_client import ApiClient
from app.infra.cache import CacheTTL
from app.infra.sqlite_repository import ResultadoRepositorySQLite
from app.reports.html_report import gerar_relatorio_html
from app.services.monitoramento_service import MonitoramentoService

app = FastAPI(
    title="Monitorador de APIs Python",
    version="1.1.0",
    description="Monitoramento assíncrono de APIs com dashboard HTML, SQLite, logs e testes.",
)

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


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "monitorador-apis-python",
        "version": "1.1.0",
        "checked_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/monitorar")
async def monitorar() -> dict:
    resultados = await service.executar(APIS_PADRAO)

    return {
        "status": "ok",
        "total": len(resultados),
        "resultados": [
            {
                "nome": item.nome,
                "url": item.url,
                "status_code": item.status_code,
                "sucesso": item.sucesso,
                "tempo_resposta_ms": item.tempo_resposta_ms,
                "status_operacional": item.status_operacional,
                "erro": item.erro,
                "consultado_em": item.consultado_em.isoformat(),
            }
            for item in resultados
        ],
    }


@app.get("/api/resultados")
def listar_resultados(limite: int = 20) -> dict:
    limite_normalizado = max(1, min(limite, 100))
    registros = repository.listar_ultimos(limite=limite_normalizado)

    return {
        "status": "ok",
        "limite": limite_normalizado,
        "total": len(registros),
        "resultados": registros,
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    resultados = await service.executar(APIS_PADRAO)
    caminho_temporario = Path("reports/dashboard_runtime.html")
    gerar_relatorio_html(resultados, caminho_temporario)
    return HTMLResponse(caminho_temporario.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = """
    <!doctype html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Monitorador de APIs Python</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #f8fafc; color: #111827; }
        header { background: #111827; color: white; padding: 28px; }
        main { max-width: 960px; margin: auto; padding: 24px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
        .card { background: white; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
        .ok { background: #dcfce7; border-color: #86efac; }
        .warn { background: #fef9c3; border-color: #fde047; }
        a { color: #005CA9; font-weight: 700; }
        code { background: #e5e7eb; padding: 2px 5px; border-radius: 5px; }
      </style>
    </head>
    <body>
      <header>
        <h1>Monitorador de APIs Python</h1>
        <p>FastAPI + dashboard HTML + health check + SQLite + logs + testes.</p>
      </header>
      <main>
        <section class="grid">
          <div class="card ok"><strong>/health</strong><br>Verificação operacional</div>
          <div class="card ok"><strong>/api/monitorar</strong><br>Executa monitoramento</div>
          <div class="card ok"><strong>/api/resultados</strong><br>Lista últimas execuções</div>
          <div class="card ok"><strong>/dashboard</strong><br>Relatório visual HTML</div>
        </section>
        <h2>Acesso rápido</h2>
        <ul>
          <li><a href="/health">Health check</a></li>
          <li><a href="/api/monitorar">Executar monitoramento JSON</a></li>
          <li><a href="/api/resultados">Resultados persistidos</a></li>
          <li><a href="/dashboard">Dashboard HTML</a></li>
          <li><a href="/docs">Swagger/OpenAPI</a></li>
        </ul>
        <p>Execução local: <code>uvicorn app.api:app --host 0.0.0.0 --port 8000</code></p>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(html)
