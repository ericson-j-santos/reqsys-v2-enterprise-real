import logging
import os
import sys
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import app.models  # noqa: F401
from app.api import (
    actions_runtime_center,
    agents,
    agile_runtime,
    auditoria,
    auth,
    codex_governado,
    cofre,
    connectors,
    dashboard,
    estatisticas,
    figma_github,
    financeiro,
    govbi,
    hub_lowcode,
    ia,
    incidentes,
    monitoramento_operacional,
    operational_autonomy,
    operational_intelligence,
    pipeline,
    processos,
    qualidade_ia,
    rag_governado,
    rastreabilidade,
    recomendacoes_ia,
    relatorios,
    requisitos,
    runtime_analytics,
    sistema,
    specs,
    teams_gateway,
    webhooks,
    wiki,
)
from app.core.config import settings
from app.core.envelope import ok
from app.core.otel import configurar_opentelemetry
from app.core.runtime_boot import build_health_payload, probe_database
from app.db import Base, engine
from app.middleware.observability import observability_middleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('reqsys.startup')
sec_logger = logging.getLogger('reqsys.security')

if settings.is_jwt_secret_weak:
    logger.warning('JWT_SECRET fraco ou padrao detectado - substitua antes de ir para producao')

settings.validate_production_gates()

Base.metadata.create_all(bind=engine)
app = FastAPI(title='ReqSys Enterprise API', version=settings.app_version)
configurar_opentelemetry(app)


@app.on_event('startup')
def warm_database_on_startup() -> None:
    ready, detail = probe_database(
        max_attempts=20 if settings.is_production else 3,
        delay_seconds=1.5 if settings.is_production else 1.0,
    )
    if ready:
        logger.info('database_startup_probe_ok detail=%s', detail)
        return
    logger.error('database_startup_probe_failed detail=%s production=%s', detail, settings.is_production)
    if settings.is_production:
        logger.warning(
            'database_startup_probe_degraded detail=%s — /health retornará 503 até o banco responder',
            detail,
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'Accept', 'X-Requested-With', 'X-Correlation-Id'],
    expose_headers=['X-Request-ID', 'X-Correlation-Id'],
)

app.include_router(auth.router)
app.include_router(requisitos.router)
app.include_router(requisitos.api_router)
app.include_router(agile_runtime.router)
app.include_router(dashboard.router)
app.include_router(estatisticas.router)
app.include_router(financeiro.router)
app.include_router(figma_github.router)
app.include_router(pipeline.router)
app.include_router(relatorios.router)
app.include_router(auditoria.router)
app.include_router(sistema.router)
app.include_router(qualidade_ia.router)
app.include_router(processos.router)
app.include_router(wiki.router)
app.include_router(specs.router)
app.include_router(cofre.router)
app.include_router(connectors.router)
app.include_router(ia.router)
app.include_router(incidentes.router)
app.include_router(recomendacoes_ia.router)
app.include_router(codex_governado.router)
app.include_router(webhooks.router)
app.include_router(rastreabilidade.router)
app.include_router(hub_lowcode.router)
app.include_router(teams_gateway.router)
app.include_router(agents.router)
app.include_router(monitoramento_operacional.router)
app.include_router(runtime_analytics.router)
app.include_router(operational_intelligence.router)
app.include_router(actions_runtime_center.router)
app.include_router(govbi.router)
app.include_router(rag_governado.router)
app.include_router(operational_autonomy.router)


@app.middleware('http')
async def observability(request: Request, call_next):
    return await observability_middleware(request, call_next)


@app.middleware('http')
async def log_security_events(request: Request, call_next):
    response = await call_next(request)
    if response.status_code in (401, 403):
        sec_logger.warning(
            'acesso negado status=%s method=%s path=%s ip=%s',
            response.status_code,
            request.method,
            request.url.path,
            request.client.host if request.client else 'unknown',
        )
    return response


def _runtime_payload(status: str, check: str) -> dict[str, str]:
    return {
        'schema_version': '1.1.0',
        'status': status,
        'check': check,
        'service': 'reqsys-api',
        'version': settings.app_version,
        'environment': settings.normalized_environment,
        'timestamp': datetime.now(UTC).isoformat(),
    }
