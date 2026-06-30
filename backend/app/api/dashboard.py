from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito
from app.services.ai_quality import calcular_resumo_qualidade_ia
from app.services.recomendacoes_ia import calcular_dashboard_ia
from app.services.requisitos_metricas import calcular_metricas_requisitos

router = APIRouter(prefix='/v1/dashboard', tags=['Dashboard'])

ENDPOINTS_PRINCIPAIS = [
    {'titulo': 'Status da API', 'url': '/health', 'metodo': 'GET'},
    {'titulo': 'Autenticação', 'url': '/v1/auth/login', 'metodo': 'POST'},
    {'titulo': 'Requisitos', 'url': '/v1/requisitos', 'metodo': 'GET/POST'},
    {'titulo': 'Qualidade IA', 'url': '/v1/qualidade-ia/resumo', 'metodo': 'GET'},
    {'titulo': 'Auditoria', 'url': '/v1/auditoria/eventos', 'metodo': 'GET'},
    {'titulo': 'Relatórios', 'url': '/v1/relatorios/ssrs', 'metodo': 'GET'},
    {'titulo': 'Informações do Sistema', 'url': '/v1/sistema/info', 'metodo': 'GET'},
]

@router.get('/requisitos')
def metricas(db: Session = Depends(get_db)):
    metricas_requisitos = calcular_metricas_requisitos(db)
    return ok({
        **metricas_requisitos,
        'endpoints_disponiveis': ENDPOINTS_PRINCIPAIS,
        'credenciais_demo': {
            'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com',
            'senha': 'admin123'
        },
        'links_uteis': {
            'documentacao_endpoints': '/v1/sistema/info',
            'health_check_completo': '/v1/sistema/health-check',
            'lista_endpoints': '/v1/sistema/endpoints'
        }
    })

@router.get('/info')
def dashboard_info(db: Session = Depends(get_db)):
    """
    Retorna informações gerais do dashboard com links para toda documentação
    """
    total_requisitos = db.query(Requisito).count()

    qualidade_ia = calcular_resumo_qualidade_ia(db)

    return ok({
        'timestamp': datetime.now(UTC).isoformat(),
        'resumo': {
            'total_requisitos': total_requisitos,
            'sistema_status': 'operacional',
            'ambiente': 'desenvolvimento'
        },
        'qualidade_ia': {
            'score_geral': qualidade_ia['score_geral'],
            'status': qualidade_ia['status'],
        },
        'endpoints_criticos': ENDPOINTS_PRINCIPAIS,
        'documentacao': {
            'info_completa': '/v1/sistema/info',
            'health_check': '/v1/sistema/health-check',
            'auditoria_config': '/v1/auditoria/eventos/config-infra',
            'relatorios': '/v1/relatorios/ssrs',
            'qualidade_ia': '/v1/qualidade-ia/resumo',
        },
        'credenciais_teste': {
            'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com',
            'senha': 'admin123'
        },
        'ambientes_urls': {
            'desenvolvimento': {
                'frontend': 'http://reqsys.local:8082',
                'api': 'http://api.reqsys.local:8210'
            },
            'producao': {
                'frontend': 'https://app.seudominio.com',
                'api': 'https://api.seudominio.com'
            }
        }
    })


@router.get('/ia')
def dashboard_ia(janela_dias: int = 30, db: Session = Depends(get_db)):
    return ok(calcular_dashboard_ia(db, janela_dias=janela_dias))

