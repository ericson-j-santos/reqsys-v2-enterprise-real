from pathlib import Path
from dotenv import load_dotenv

# Carrega .env da raiz do projeto (um nível acima de backend/)
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, requisitos, dashboard, pipeline, relatorios, auditoria, sistema, qualidade_ia
from app.core.config import settings
from app.core.envelope import ok
from app.db import Base, engine
from app.models import requisito, auditoria as auditoria_model, ai_quality as ai_quality_model

Base.metadata.create_all(bind=engine)
app = FastAPI(title='ReqSys Enterprise API', version='2.6.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(auth.router)
app.include_router(requisitos.router)
app.include_router(dashboard.router)
app.include_router(pipeline.router)
app.include_router(relatorios.router)
app.include_router(auditoria.router)
app.include_router(sistema.router)
app.include_router(qualidade_ia.router)

@app.get('/health')
def health():
    return ok({'status': 'ok', 'service': 'reqsys-api'})
