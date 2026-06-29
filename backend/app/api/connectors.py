from fastapi import APIRouter, Header

from app.core.envelope import ok

router = APIRouter(tags=['Connection Broker'])

_CONECTORES_DEMO = [
    {
        'ambiente': 'dev',
        'conector': 'repository_provider',
        'capability': 'repository.read',
        'status': 'ready',
        'criticidade': 'high',
        'acao_sugerida': 'Executar com auditoria.',
        'requires_human_confirmation': False,
    },
    {
        'ambiente': 'homolog',
        'conector': 'repository_provider',
        'capability': 'repository.write',
        'status': 'missing_permission',
        'criticidade': 'critical',
        'acao_sugerida': 'Solicitar autorização contextual antes da escrita.',
        'requires_human_confirmation': True,
    },
    {
        'ambiente': 'dev',
        'conector': 'figma_provider',
        'capability': 'design.read',
        'status': 'misconfigured',
        'criticidade': 'medium',
        'acao_sugerida': 'Configurar FIGMA_ACCESS_TOKEN ou usar modo degradado local.',
        'requires_human_confirmation': False,
    },
    {
        'ambiente': 'prod',
        'conector': 'document_provider',
        'capability': 'document.read',
        'status': 'ready',
        'criticidade': 'medium',
        'acao_sugerida': 'Manter health-check periódico.',
        'requires_human_confirmation': False,
    },
    {
        'ambiente': 'prod',
        'conector': 'communication_provider',
        'capability': 'message.compose',
        'status': 'blocked',
        'criticidade': 'high',
        'acao_sugerida': 'Exigir confirmação humana antes do envio.',
        'requires_human_confirmation': True,
    },
]


def _resolver_correlation_id(header_correlation: str | None, header_request: str | None) -> str:
    for candidate in (header_correlation, header_request):
        if candidate and candidate.strip():
            return candidate.strip()
    from uuid import uuid4

    return f'reqsys-conn-{uuid4()}'


def _resumo_conectores(conectores: list[dict]) -> dict:
    bloqueados = sum(1 for item in conectores if item['status'] in {'blocked', 'unavailable', 'misconfigured'})
    pendentes = sum(1 for item in conectores if item['status'] in {'missing_permission', 'insufficient_permission', 'expired'})
    prontos = sum(1 for item in conectores if item['status'] == 'ready')
    if bloqueados:
        estado_geral = 'bloqueado'
    elif pendentes:
        estado_geral = 'amarelo'
    else:
        estado_geral = 'verde'
    return {
        'total': len(conectores),
        'prontos': prontos,
        'pendentes': pendentes,
        'bloqueados': bloqueados,
        'estado_geral': estado_geral,
    }


@router.get('/api/connectors/health')
def obter_connectors_health(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    conectores = list(_CONECTORES_DEMO)
    return ok(
        {
            'correlation_id': correlation_id,
            'conectores': conectores,
            'resumo': _resumo_conectores(conectores),
        },
        correlation_id,
    )
