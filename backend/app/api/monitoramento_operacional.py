from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.envelope import ok

router = APIRouter(tags=['Monitoramento Operacional'])

ESTADOS_VALIDOS = {'verde', 'amarelo', 'vermelho', 'bloqueado', 'desconhecido'}
SEVERIDADES_VALIDAS = {'baixa', 'media', 'alta', 'critica'}


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
            tipo='pull_request',
            referencia='REQSYS-OPER-005',
            titulo='Implementar /monitoramento-operacional no ReqSys',
            estado='amarelo',
            severidade='media',
            origem='reqsys',
            pronto_para_merge=False,
            bloqueante=False,
            detalhes={
                'motivo': 'incremento em implementacao',
                'regra': 'ci_verde_necessario_mas_nao_suficiente',
            },
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatorios de producao',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            pronto_para_merge=False,
            bloqueante=False,
            detalhes={
                'auth': 'obrigatoria',
                'cors': 'restrito',
                'jwt': 'issuer_audience_obrigatorios',
                'logs': 'sem_dados_sensiveis',
            },
        ),
    ]
    estado_geral = classificar_estado_geral(itens)
    return MonitoramentoOperacional(
        correlation_id=correlation_id,
        coletado_em=datetime.now(timezone.utc).isoformat(),
        ambiente='dev',
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
