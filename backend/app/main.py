import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — garante create_all para integracao_log e configuracao_lowcode
from app.api import (
    agents,
    auditoria,
    auth,
    cofre,
    dashboard,
    estatisticas,
    figma_github,
    hub_lowcode,
    ia,
    monitoramento_operacional,
    pipeline,
    processos,
    qualidade_ia,
    rastreabilidade,
    relatorios,
    requisitos,
    sistema,
    specs,
    webhooks,
    wiki,
)
from app.core.config import settings
from app.core.envelope import ok
from app.db import Base, engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('reqsys.startup')
sec_logger = logging.getLogger('reqsys.security')

if settings.is_jwt_secret_weak:
    logger.warning('JWT_SECRET fraco ou padrao detectado — substitua antes de ir para producao')

settings.validate_production_gates()

Base.metadata.create_all(bind=engine)
app = FastAPI(title='ReqSys Enterprise API', version=settings.app_version)

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
app.include_router(dashboard.router)
app.include_router(estatisticas.router)
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
app.include_router(ia.router)
app.include_router(webhooks.router)
app.include_router(rastreabilidade.router)
app.include_router(hub_lowcode.router)
app.include_router(agents.router)
app.include_router(monitoramento_operacional.router)


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


@app.get('/health')
def health():
    return ok({'status': 'ok', 'service': 'reqsys-api'})
