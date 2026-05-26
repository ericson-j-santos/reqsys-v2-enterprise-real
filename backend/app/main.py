import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import auth, requisitos, dashboard, pipeline, relatorios, auditoria, sistema, qualidade_ia, processos, wiki, specs, cofre
from app.core.config import settings
from app.core.envelope import ok
from app.db import Base, engine
from app.models import requisito, auditoria as auditoria_model, ai_quality as ai_quality_model

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('reqsys.startup')
sec_logger = logging.getLogger('reqsys.security')

_WEAK_SECRETS = {'trocar-em-producao', 'secret', 'changeme', 'TROQUE-POR-UM-SEGREDO-FORTE-MINIMO-32-CHARS', ''}
if settings.jwt_secret in _WEAK_SECRETS or len(settings.jwt_secret) < 32:
    logger.warning('JWT_SECRET fraco ou padrao detectado — substitua antes de ir para producao')

Base.metadata.create_all(bind=engine)
app = FastAPI(title='ReqSys Enterprise API', version='2.8.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'Accept', 'X-Requested-With'],
    expose_headers=['X-Request-ID'],
)

app.include_router(auth.router)
app.include_router(requisitos.router)
app.include_router(dashboard.router)
app.include_router(pipeline.router)
app.include_router(relatorios.router)
app.include_router(auditoria.router)
app.include_router(sistema.router)
app.include_router(qualidade_ia.router)
app.include_router(processos.router)
app.include_router(wiki.router)
app.include_router(specs.router)
app.include_router(cofre.router)


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
