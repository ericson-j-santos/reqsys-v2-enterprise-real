import logging
import os
import sys
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import app.models  # noqa: F401
from app.api import (
    actions_runtime_center,
    agents,
    agile_runtime,
    auditoria,
    auth,
    codex_governado,
    cofre,
    dashboard,
    estatisticas,
    figma_github,
    govbi,
    hub_lowcode,
    ia,
    monitoramento_operacional,
    operational_intelligence,
    pipeline,
    processos,
    qualidade_ia,
    rag_governado,
    rastreabilidade,
    relatorios,
    requisitos,
    runtime_analytics,
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
    logger.warning('JWT_SECRET fraco ou padrao detectado - substitua antes de ir para producao')

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
app.include_router(agile_runtime.router)
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
app.include_router(codex_governado.router)
app.include_router(webhooks.router)
app.include_router(rastreabilidade.router)
app.include_router(hub_lowcode.router)
app.include_router(agents.router)
app.include_router(monitoramento_operacional.router)
app.include_router(runtime_analytics.router)
app.include_router(operational_intelligence.router)
app.include_router(actions_runtime_center.router)
app.include_router(govbi.router)
app.include_router(rag_governado.router)


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
        'status': status,
        'check': check,
        'service': 'reqsys-api',
        'version': settings.app_version,
        'environment': settings.normalized_environment,
        'timestamp': datetime.now(UTC).isoformat(),
    }


def _build_sha() -> str:
    return os.getenv('GITHUB_SHA') or os.getenv('FLY_IMAGE_REF') or 'unknown'


def _runtime_contracts() -> dict:
    return {
        'schema_version': '1.0.0',
        'contract': 'reqsys-public-runtime-contract',
        'service': 'reqsys-api',
        'environment': settings.normalized_environment,
        'version': settings.app_version,
        'required_public_endpoints': [
            {'method': 'GET', 'path': '/health', 'expected_http': 200, 'purpose': 'basic_health'},
            {'method': 'GET', 'path': '/api/runtime/health', 'expected_http': 200, 'purpose': 'runtime_health'},
            {'method': 'GET', 'path': '/api/runtime/readiness', 'expected_http': 200, 'purpose': 'traffic_readiness'},
            {'method': 'GET', 'path': '/api/runtime/liveness', 'expected_http': 200, 'purpose': 'process_liveness'},
        ],
        'optional_public_evidence': [
            {'method': 'GET', 'path': '/', 'purpose': 'public_landing'},
            {'method': 'GET', 'path': '/runtime', 'purpose': 'runtime_operational_page'},
            {'method': 'GET', 'path': '/api/runtime/contracts', 'purpose': 'runtime_contract'},
            {'method': 'GET', 'path': '/api/runtime/version', 'purpose': 'runtime_version'},
            {'method': 'GET', 'path': '/api/runtime/build-info', 'purpose': 'runtime_build'},
            {'method': 'GET', 'path': '/api/runtime/dependencies', 'purpose': 'runtime_dependencies'},
        ],
    }


def _runtime_html() -> str:
    generated_at = datetime.now(UTC).isoformat()
    cards = [
        ('Health', '/health', 'Disponibilidade básica'),
        ('Runtime Health', '/api/runtime/health', 'Saúde operacional'),
        ('Readiness', '/api/runtime/readiness', 'Pronto para tráfego'),
        ('Liveness', '/api/runtime/liveness', 'Processo ativo'),
        ('Contracts', '/api/runtime/contracts', 'Contrato JSON'),
        ('Version', '/api/runtime/version', 'Versão pública'),
        ('Build Info', '/api/runtime/build-info', 'Build e deploy'),
        ('Dependencies', '/api/runtime/dependencies', 'Dependências'),
    ]
    cards_html = ''.join(
        f"<article class='card'><strong>{title}</strong><span>{description}</span><a href='{href}'>{href}</a></article>"
        for title, href, description in cards
    )
    return f"""<!doctype html>
<html lang='pt-BR'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>ReqSys Runtime</title>
  <style>
    body {{ margin:0; padding:24px; font-family:Arial,sans-serif; background:#0f172a; color:#e5e7eb; }}
    main {{ max-width:1100px; margin:0 auto; }}
    .hero {{ border:1px solid #334155; border-radius:16px; padding:20px; background:#111827; margin-bottom:16px; }}
    .status {{ color:#22c55e; font-weight:700; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
    .card {{ display:flex; flex-direction:column; gap:8px; border:1px solid #334155; border-radius:14px; padding:16px; background:#020617; }}
    .card span, small {{ color:#94a3b8; }}
    a {{ color:#38bdf8; word-break:break-word; }}
  </style>
</head>
<body>
  <main>
    <section class='hero'>
      <h1>ReqSys Runtime Operational Page</h1>
      <p class='status'>Status público governado</p>
      <small>Environment: {settings.normalized_environment} · Version: {settings.app_version} · Build: {_build_sha()} · Generated: {generated_at}</small>
    </section>
    <section class='grid'>{cards_html}</section>
  </main>
</body>
</html>"""


@app.get('/runtime', response_class=HTMLResponse)
def runtime_page():
    return HTMLResponse(_runtime_html())


@app.get('/')
def root():
    return ok(
        {
            'status': 'ok',
            'service': 'reqsys-api',
            'version': settings.app_version,
            'environment': settings.normalized_environment,
            'docs': '/docs',
            'health': '/health',
            'runtime_page': '/runtime',
            'runtime_health': '/api/runtime/health',
            'runtime_readiness': '/api/runtime/readiness',
            'runtime_liveness': '/api/runtime/liveness',
            'runtime_metrics': '/api/runtime/metrics',
            'runtime_dashboard': '/api/runtime/dashboard',
            'runtime_analytics': '/api/runtime/analytics',
            'runtime_contracts': '/api/runtime/contracts',
            'runtime_version': '/api/runtime/version',
            'runtime_build_info': '/api/runtime/build-info',
            'runtime_dependencies': '/api/runtime/dependencies',
            'agile_runtime': '/v1/agile-runtime/resumo',
        }
    )


@app.get('/health')
def health():
    return ok({'status': 'ok', 'service': 'reqsys-api'})


@app.get('/api/runtime/health')
def runtime_health():
    return ok(_runtime_payload('ok', 'health'))


@app.get('/api/runtime/readiness')
def runtime_readiness():
    return ok(_runtime_payload('ready', 'readiness'))


@app.get('/api/runtime/liveness')
def runtime_liveness():
    return ok(_runtime_payload('alive', 'liveness'))


@app.get('/api/runtime/contracts')
def runtime_contracts():
    return ok(_runtime_contracts())


@app.get('/api/runtime/version')
def runtime_version():
    return ok(
        {
            'service': 'reqsys-api',
            'version': settings.app_version,
            'environment': settings.normalized_environment,
            'schema_version': '1.0.0',
        }
    )


@app.get('/api/runtime/build-info')
def runtime_build_info():
    return ok(
        {
            'service': 'reqsys-api',
            'version': settings.app_version,
            'environment': settings.normalized_environment,
            'build_sha': _build_sha(),
            'generated_at': datetime.now(UTC).isoformat(),
        }
    )


@app.get('/api/runtime/dependencies')
def runtime_dependencies():
    return ok(
        {
            'service': 'reqsys-api',
            'status': 'ok',
            'dependencies': [
                {'name': 'api', 'type': 'process', 'status': 'ok', 'required': True},
                {'name': 'database', 'type': 'storage', 'status': 'not_checked', 'required': True},
                {'name': 'identity', 'type': 'external', 'status': 'not_checked', 'required': False},
            ],
        }
    )
