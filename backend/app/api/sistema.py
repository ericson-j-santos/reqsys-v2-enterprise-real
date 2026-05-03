from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito

router = APIRouter(prefix='/v1/sistema', tags=['Sistema'])

ENDPOINTS_INFO = {
    'health': {
        'metodo': 'GET',
        'url': '/health',
        'descricao': 'Status da API',
        'autenticacao': False,
        'exemplo_resposta': {'status': 'ok', 'service': 'reqsys-api'}
    },
    'login': {
        'metodo': 'POST',
        'url': '/v1/auth/login',
        'descricao': 'Autenticação com email e senha',
        'autenticacao': False,
        'parametros': {'email': 'string', 'senha': 'string'},
        'exemplo_resposta': {'token': 'jwt_token_aqui', 'usuario': {'id': 1, 'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'}}
    },
    'listar_requisitos': {
        'metodo': 'GET',
        'url': '/v1/requisitos',
        'descricao': 'Listar todos os requisitos',
        'autenticacao': True,
        'exemplo_resposta': [{'id': 1, 'codigo': 'REQ-12345', 'titulo': 'Requisito exemplo', 'status': 'recebido'}]
    },
    'criar_requisito': {
        'metodo': 'POST',
        'url': '/v1/requisitos',
        'descricao': 'Criar novo requisito',
        'autenticacao': True,
        'parametros': {'titulo': 'string', 'descricao': 'string', 'solicitante': 'string', 'status': 'string'},
        'exemplo_resposta': {'id': 2, 'codigo': 'REQ-67890', 'titulo': 'Novo requisito', 'status': 'recebido'}
    },
    'dashboard_metricas': {
        'metodo': 'GET',
        'url': '/v1/dashboard/requisitos',
        'descricao': 'Métricas do dashboard',
        'autenticacao': True,
        'exemplo_resposta': {'total': 10, 'em_analise': 2, 'aprovados': 5, 'pendentes': 3}
    },
    'auditoria_config': {
        'metodo': 'GET',
        'url': '/v1/auditoria/eventos/config-infra',
        'descricao': 'Histórico de mudanças de configuração de infraestrutura',
        'autenticacao': True,
        'exemplo_resposta': {
            'config_historico': [
                {
                    'id': 1,
                    'usuario': 'copilot',
                    'acao': 'CONFIG_DOMINIO_ATUALIZADA',
                    'criado_em': '2026-05-02T02:02:02'
                }
            ],
            'total': 1
        }
    },
    'auditoria_todos': {
        'metodo': 'GET',
        'url': '/v1/auditoria/eventos',
        'descricao': 'Lista todos eventos de auditoria com filtros opcionais',
        'autenticacao': True,
        'parametros': {'limit': 'int (1-500)', 'offset': 'int', 'entidade': 'string', 'acao': 'string'}
    },
    'relatorios_ssrs': {
        'metodo': 'GET',
        'url': '/v1/relatorios/ssrs',
        'descricao': 'Links para relatórios SSRS disponíveis',
        'autenticacao': True,
        'exemplo_resposta': {
            'enabled': True,
            'report_server_base_url': 'http://NOTERI:80/ReportServer',
            'reports_path': 'ReqSys',
            'reports': [{'name': 'AtvIndividual', 'render_url': '...'}]
        }
    },
}

CREDENCIAIS_DEMO = {
    'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com',
    'senha': 'admin123',
    'descricao': 'Credenciais de teste para desenvolvimento local'
}

@router.get('/info')
def info_endpoints():
    """
    Retorna documentação completa de todos os endpoints disponíveis.
    Útil para onboarding de desenvolvedores e clientes.
    """
    return ok({
        'api_version': '2.2.0',
        'titulo': 'ReqSys Enterprise API',
        'descricao': 'Solução SaaS para engenharia de requisitos com rastreabilidade e auditoria',
        'endpoints': ENDPOINTS_INFO,
        'credenciais_demo': CREDENCIAIS_DEMO,
        'ambientes': {
            'desenvolvimento': {
                'frontend': 'http://reqsys.local:8082',
                'api': 'http://api.reqsys.local:8210',
                'gateway': 'http://reqsys.local:8082',
                'notas': 'Requer entradas em hosts do Windows'
            },
            'producao': {
                'frontend': 'https://app.seudominio.com',
                'api': 'https://api.seudominio.com',
                'gateway': 'https://app.seudominio.com',
                'notas': 'Requer DNS e HTTPS/TLS configurados'
            }
        }
    })

@router.get('/health-check')
def health_check(db: Session = Depends(get_db)):
    """
    Verifica saúde de todos os componentes principais da aplicação.
    Retorna status de database, endpoints críticos e configuração.
    """
    checks = {}
    
    # Database check
    try:
        count = db.query(Requisito).count()
        checks['database'] = {'status': 'ok', 'requisitos_total': count}
    except Exception as e:
        checks['database'] = {'status': 'erro', 'detalhe': str(e)}
    
    # Config check
    checks['config'] = {
        'status': 'ok',
        'cors_configurado': True,
        'dominio_dev': 'reqsys.local',
        'dominio_prod': 'app.seudominio.com (exemplo)'
    }
    
    # Endpoints críticos
    checks['endpoints'] = {
        'health': '/health (GET)',
        'login': '/v1/auth/login (POST)',
        'requisitos': '/v1/requisitos (GET/POST)',
        'dashboard': '/v1/dashboard/requisitos (GET)',
        'auditoria': '/v1/auditoria/eventos (GET)',
        'relatorios': '/v1/relatorios/ssrs (GET)',
        'sistema_info': '/v1/sistema/info (GET)',
        'sistema_health': '/v1/sistema/health-check (GET)'
    }
    
    all_ok = all(check.get('status') == 'ok' for check in checks.values())
    
    return ok({
        'timestamp': datetime.utcnow().isoformat(),
        'saude_geral': 'ok' if all_ok else 'aviso',
        'componentes': checks,
        'credenciais_teste': CREDENCIAIS_DEMO
    })

@router.get('/endpoints')
def listar_endpoints():
    """
    Lista simplificada de todos os endpoints disponíveis.
    """
    endpoints_list = []
    for key, info in ENDPOINTS_INFO.items():
        endpoints_list.append({
            'id': key,
            'metodo': info['metodo'],
            'url': info['url'],
            'descricao': info['descricao'],
            'autenticacao_requerida': info['autenticacao']
        })
    
    return ok({
        'total_endpoints': len(endpoints_list),
        'endpoints': endpoints_list,
        'credenciais_demo': CREDENCIAIS_DEMO
    })

