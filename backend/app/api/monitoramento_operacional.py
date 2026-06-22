"""API de monitoramento operacional do ReqSys."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.envelope import ok

router = APIRouter(tags=['Monitoramento Operacional'])


class ItemMonitorado(BaseModel):
    """Item individual acompanhado pelo painel operacional."""

    tipo: str
    referencia: str
    titulo: str
    estado: str = Field(pattern='^(verde|amarelo|vermelho|bloqueado|desconhecido)$')
    severidade: str = Field(pattern='^(baixa|media|alta|critica)$')
    origem: str
    pronto_para_merge: bool = False
    bloqueante: bool = False
    proximo_passo: str | None = None
    criterio_de_fechamento: str | None = None
    detalhes: dict = Field(default_factory=dict)


class ResumoMonitoramento(BaseModel):
    """Resumo agregado do monitoramento operacional."""

    estado_geral: str
    bloqueios: int
    pendencias: int
    total_itens: int
    frentes_criticas: int = 0
    itens_prontos_para_merge: int = 0


class TempoOperacional(BaseModel):
    """Métricas estimadas de tempo para próxima ação operacional."""

    previsao_proxima_acao: str
    eta_proxima_verificacao_minutos: int
    tempo_medio_proxima_acao_minutos: int
    tempo_medio_resolucao_horas: float
    tempo_medio_review_minutos: int
    sla_operacional_minutos: int


class MonitoramentoOperacional(BaseModel):
    """Contrato versionado do snapshot operacional."""

    schema_version: str = '1.2.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    resumo: ResumoMonitoramento
    tempo_operacional: TempoOperacional
    itens: list[ItemMonitorado]


def classificar_estado_geral(itens: list[ItemMonitorado]) -> str:
    """Classifica o estado geral com precedência para bloqueios."""

    if not itens:
        return 'desconhecido'
    if any(item.estado == 'bloqueado' or item.bloqueante for item in itens):
        return 'bloqueado'
    if any(item.estado == 'vermelho' for item in itens):
        return 'vermelho'
    if any(item.estado in {'amarelo', 'desconhecido'} for item in itens):
        return 'amarelo'
    return 'verde'


def criar_tempo_operacional(estado_geral: str) -> TempoOperacional:
    """Define ETA médio da próxima ação com base no estado geral atual."""

    if estado_geral == 'bloqueado':
        return TempoOperacional(
            previsao_proxima_acao='Tratar bloqueio operacional prioritário antes de avançar.',
            eta_proxima_verificacao_minutos=10,
            tempo_medio_proxima_acao_minutos=15,
            tempo_medio_resolucao_horas=4.0,
            tempo_medio_review_minutos=30,
            sla_operacional_minutos=60,
        )
    if estado_geral in {'vermelho', 'amarelo'}:
        return TempoOperacional(
            previsao_proxima_acao='Revalidar CI, revisão e pendências antes de prosseguir.',
            eta_proxima_verificacao_minutos=15,
            tempo_medio_proxima_acao_minutos=20,
            tempo_medio_resolucao_horas=6.0,
            tempo_medio_review_minutos=45,
            sla_operacional_minutos=120,
        )
    return TempoOperacional(
        previsao_proxima_acao='Manter monitoramento e preparar próxima frente segura.',
        eta_proxima_verificacao_minutos=30,
        tempo_medio_proxima_acao_minutos=30,
        tempo_medio_resolucao_horas=2.0,
        tempo_medio_review_minutos=20,
        sla_operacional_minutos=240,
    )


def criar_snapshot_minimo(correlation_id: str) -> MonitoramentoOperacional:
    """Monta snapshot determinístico das frentes estratégicas do ReqSys."""

    itens = [
        ItemMonitorado(
            tipo='frente',
            referencia='REQSYS-OPER-005',
            titulo='Monitoramento operacional publicado',
            estado='verde',
            severidade='media',
            origem='issue-46/pr-50',
            pronto_para_merge=True,
            criterio_de_fechamento='Endpoint, tela, rota e testes publicados na main.',
            detalhes={'status': 'primeira fatia funcional mergeada'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-001',
            titulo='GovBI IA com grounding e falha controlada',
            estado='vermelho',
            severidade='alta',
            origem='issue-30',
            bloqueante=True,
            proximo_passo='Mapear contrato real, exigir fontes e tratar falha sem ambiguidade.',
            criterio_de_fechamento='Consulta retorna fontes válidas ou erro 422 auditável.',
            detalhes={
                'gates': ['correlation_id', 'fontes_obrigatorias', 'resposta_auditavel'],
                'risco': 'consulta operacional ainda não confiável',
            },
        ),
        ItemMonitorado(
            tipo='frontend',
            referencia='REQSYS-OPER-002',
            titulo='Dashboard para Analítico filtrado',
            estado='amarelo',
            severidade='media',
            origem='issue-31',
            proximo_passo='Padronizar deep link, filtros persistidos e rota analítica compartilhável.',
            criterio_de_fechamento='Cards abrem analítico com filtros preservados na URL.',
            detalhes={'padrao': 'Schema-Driven UI / Dynamic Data Renderer'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-003',
            titulo='Planner via Low Code e API',
            estado='amarelo',
            severidade='alta',
            origem='issue-32',
            proximo_passo='Implementar idempotência, retry, registro de falha e reprocessamento.',
            criterio_de_fechamento='Reenvio do mesmo payload não duplica tarefa no Planner.',
            detalhes={'gates': ['idempotencia', 'retry_controlado', 'token_refresh']},
        ),
        ItemMonitorado(
            tipo='pipeline',
            referencia='REQSYS-OPER-004',
            titulo='Pipeline operacional e CI/CD',
            estado='amarelo',
            severidade='critica',
            origem='issue-33',
            proximo_passo='Unificar gates, publicar evidências e histórico operacional do CI.',
            criterio_de_fechamento='CI publica artifact de evidência e bloqueia merge inseguro.',
            detalhes={'gates': ['ruff', 'pytest', 'coverage', 'bandit', 'pip-audit', 'e2e']},
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatórios de produção',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            pronto_para_merge=True,
            criterio_de_fechamento='Configurações inseguras bloqueiam inicialização em produção.',
            detalhes={'validacao': 'auth, CORS, JWT, PII e auditoria protegidos por gates'},
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
            frentes_criticas=sum(1 for item in itens if item.severidade == 'critica'),
            itens_prontos_para_merge=sum(1 for item in itens if item.pronto_para_merge),
        ),
        tempo_operacional=criar_tempo_operacional(estado_geral),
        itens=itens,
    )


@router.get('/monitoramento-operacional')
def obter_monitoramento_operacional(x_correlation_id: str | None = Header(default=None)):
    """Retorna o snapshot operacional com correlation_id propagado ou gerado."""

    correlation_id = x_correlation_id or str(uuid4())
    snapshot = criar_snapshot_minimo(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)
