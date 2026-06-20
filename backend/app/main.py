import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.models  # noqa: F401 — garante create_all para integracao_log e configuracao_lowcode
from app.api import (
    agents,
    auditoria,
    auth,
    cofre,
    dashboard,
    figma_github,
    hub_lowcode,
    ia,
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
    allow_headers=['Authorization', 'Content-Type', 'Accept', 'X-Requested-With', 'X-Correlation-Id', 'X-Correlation-ID'],
    expose_headers=['X-Request-ID', 'X-Correlation-Id', 'X-Correlation-ID'],
)

app.include_router(auth.router)
app.include_router(requisitos.router)
app.include_router(dashboard.router)
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


@app.middleware('http')
async def observability_and_security_headers(request: Request, call_next):
    started_at = time.perf_counter()
    correlation_id = (
        request.headers.get('X-Correlation-ID')
        or request.headers.get('X-Correlation-Id')
        or request.headers.get('X-Request-ID')
        or str(uuid.uuid4())
    )
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

    response.headers['X-Correlation-ID'] = correlation_id
    response.headers['X-Request-ID'] = correlation_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.url.scheme == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    logger.info(
        'http_request method=%s path=%s status=%s elapsed_ms=%s correlation_id=%s',
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        correlation_id,
    )
    return response


@app.middleware('http')
async def log_security_events(request: Request, call_next):
    response = await call_next(request)
    if response.status_code in (401, 403):
        sec_logger.warning(
            'acesso negado status=%s method=%s path=%s ip=%s correlation_id=%s',
            response.status_code,
            request.method,
            request.url.path,
            request.client.host if request.client else 'unknown',
            getattr(request.state, 'correlation_id', None),
        )
    return response


@app.get('/health')
def health():
    return ok({'status': 'ok', 'service': 'reqsys-api'})


@app.get('/health/live')
def health_live():
    return ok({'status': 'alive', 'service': 'reqsys-api'})


@app.get('/health/ready')
def health_ready():
    checks = {'database': 'unknown'}
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception as exc:  # pragma: no cover - depende do ambiente de infraestrutura
        logger.exception('readiness_check_failed database=%s', exc)
        checks['database'] = 'error'

    status = 'ready' if all(value == 'ok' for value in checks.values()) else 'degraded'
    return ok({'status': status, 'service': 'reqsys-api', 'checks': checks})
