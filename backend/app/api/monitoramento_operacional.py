from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.autonomous_operations import gerar_snapshot_operacao_autonoma
from app.core.config import settings
from app.core.envelope import ok
from app.core.runtime_remediation import (
    RemediationRequest,
    avaliar_remediacao,
    criar_health_snapshot_base,
)

router = APIRouter(tags=['Monitoramento Operacional'])


class ItemMonitorado(BaseModel):
    tipo: str
    referencia: str
    titulo: str
    estado: str = Field(pattern='^(verde|amarelo|vermelho|bloqueado|desconhecido)$')
    severidade: str = Field(pattern='^(baixa|media|alta|critica)$')
    origem: str
    pronto_para_merge: bool = False
    bloqueante: bool = False
    detalhes: dict = Field(default_factory=dict)


class ResumoMonitoramento(BaseModel):
    estado_geral: str
    bloqueios: int
    pendencias: int
    total_itens: int


class MonitoramentoOperacional(BaseModel):
    schema_version: str = '1.0.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    resumo: ResumoMonitoramento
    itens: list[ItemMonitorado]


def classificar_estado_geral(itens: list[ItemMonitorado]) -> str:
    if not itens:
        return 'desconhecido'
    if any(item.estado == 'bloqueado' or item.bloqueante for item in itens):
        return 'bloqueado'
    if any(item.estado == 'vermelho' for item in itens):
        return 'vermelho'
    if any(item.estado in {'amarelo', 'desconhecido'} for item in itens):
        return 'amarelo'
    return 'verde'


def criar_snapshot_minimo(correlation_id: str) -> MonitoramentoOperacional:
    itens = [
        ItemMonitorado(
            tipo='frente',
            referencia='REQSYS-OPER-005',
            titulo='Implementar monitoramento operacional',
            estado='amarelo',
            severidade='media',
            origem='issue-46',
            detalhes={'motivo': 'primeira fatia funcional em validacao'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-001',
            titulo='GovBI IA',
            estado='vermelho',
            severidade='alta',
            origem='issue-30',
            detalhes={'motivo': 'consulta operacional ainda pendente'},
        ),
        ItemMonitorado(
            tipo='frontend',
            referencia='REQSYS-OPER-002',
            titulo='Dashboard para Analitico filtrado',
            estado='amarelo',
            severidade='media',
            origem='issue-31',
            detalhes={'motivo': 'deep link e filtros ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-003',
            titulo='Planner via Low Code e API',
            estado='amarelo',
            severidade='alta',
            origem='issue-32',
            detalhes={'motivo': 'contrato e idempotencia ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='pipeline',
            referencia='REQSYS-OPER-004',
            titulo='Pipeline operacional e CI',
            estado='amarelo',
            severidade='critica',
            origem='issue-33',
            detalhes={'motivo': 'evidencias automatizadas ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatorios de producao',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            detalhes={'validacao': 'configuracoes inseguras bloqueiam producao'},
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-1',
            titulo='Autonomous Operations Platform - maturidade e politicas governadas',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            detalhes={
                'motivo': 'maturity score e policies implementadas; execucao destrutiva permanece bloqueada por governanca',
                'endpoint': '/operacao-autonoma/maturidade',
            },
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-2',
            titulo='Runtime Health Validator e Executor Governado de Remediacao',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            detalhes={
                'motivo': 'health validator e executor dry-run implementados; acoes destrutivas seguem bloqueadas por politica',
                'endpoints': ['/operacao-autonoma/runtime-health', '/operacao-autonoma/remediacoes/avaliar'],
            },
        ),
    ]
    estado_geral = classificar_estado_geral(itens)
    return MonitoramentoOperacional(
        correlation_id=correlation_id,
        coletado_em=datetime.now(timezone.utc).isoformat(),
        ambiente=settings.normalized_environment,
        resumo=ResumoMonitoramento(
            estado_geral=estado_geral,
            bloqueios=sum(1 for item in itens if item.estado == 'bloqueado' or item.bloqueante),
            pendencias=sum(1 for item in itens if item.estado in {'amarelo', 'vermelho', 'desconhecido'}),
            total_itens=len(itens),
        ),
        itens=itens,
    )


@router.get('/monitoramento-operacional')
def obter_monitoramento_operacional(x_correlation_id: str | None = Header(default=None)):
    correlation_id = x_correlation_id or str(uuid4())
    snapshot = criar_snapshot_minimo(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)


@router.get('/operacao-autonoma/maturidade')
def obter_maturidade_operacao_autonoma(x_correlation_id: str | None = Header(default=None)):
    correlation_id = x_correlation_id or str(uuid4())
    snapshot = gerar_snapshot_operacao_autonoma(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)


@router.get('/operacao-autonoma/runtime-health')
def obter_runtime_health(x_correlation_id: str | None = Header(default=None)):
    correlation_id = x_correlation_id or str(uuid4())
    snapshot = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    return ok(snapshot.model_dump(), correlation_id)


@router.post('/operacao-autonoma/remediacoes/avaliar')
def avaliar_remediacao_governada(payload: RemediationRequest, x_correlation_id: str | None = Header(default=None)):
    correlation_id = x_correlation_id or str(uuid4())
    health_snapshot = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    decisao = avaliar_remediacao(payload, health_snapshot, correlation_id)
    return ok(decisao.model_dump(), correlation_id)
