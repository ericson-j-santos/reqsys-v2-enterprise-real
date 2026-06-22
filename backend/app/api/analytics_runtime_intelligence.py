from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.envelope import ok

router = APIRouter(prefix='/v1/analytics-runtime-intelligence', tags=['Analytics Runtime Intelligence'])


class AriValidationItem(BaseModel):
    codigo: str
    nome: str
    categoria: str
    status: Literal['ok', 'warn', 'fail', 'block'] = 'ok'
    score: int = Field(ge=0, le=100)
    evidencia: str
    acao_recomendada: str


class AriRuntimeSnapshot(BaseModel):
    capability: str
    posicao_estrategica: str
    health_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    ai_governance_score: int = Field(ge=0, le=100)
    operational_quality_score: int = Field(ge=0, le=100)
    ambiente: str
    atualizado_em: str
    validacoes: list[AriValidationItem]
    guard_rails: list[dict[str, str]]
    figma: dict[str, str]
    proximas_acoes: list[str]


def _validacoes_base() -> list[AriValidationItem]:
    return [
        AriValidationItem(
            codigo='COUNT_BEFORE_AFTER',
            nome='Comparar totais antes/depois',
            categoria='Volume',
            score=96,
            evidencia='Checkpoint de contagem habilitado para origem, staging e destino.',
            acao_recomendada='Manter limite de divergencia parametrizado por dominio.',
        ),
        AriValidationItem(
            codigo='STAT_EXTREMES',
            nome='Validar extremos e medias',
            categoria='Estatistica',
            status='warn',
            score=88,
            evidencia='MIN, MAX e AVG consolidados no runtime; thresholds dinamicos pendentes por dominio.',
            acao_recomendada='Versionar limites de anomalia por indicador critico.',
        ),
        AriValidationItem(
            codigo='FILTER_ISOLATION',
            nome='Testar filtros separadamente',
            categoria='Query Intelligence',
            score=93,
            evidencia='Fluxo incremental de filtros definido para troubleshooting analitico.',
            acao_recomendada='Persistir impacto percentual por filtro.',
        ),
        AriValidationItem(
            codigo='JOIN_CARDINALITY',
            nome='Validar JOINs utilizados',
            categoria='Relacionamento',
            status='warn',
            score=87,
            evidencia='Validador de cardinalidade especificado; bloqueio de explosao cartesiana definido como gate.',
            acao_recomendada='Coletar baseline real por consulta produtiva.',
        ),
        AriValidationItem(
            codigo='NULL_CRITICAL',
            nome='Procurar nulos indevidos',
            categoria='Data Quality',
            score=95,
            evidencia='Classificacao de null critico, esperado e operacional definida.',
            acao_recomendada='Conectar catalogo de campos obrigatorios.',
        ),
        AriValidationItem(
            codigo='RECONCILIATION',
            nome='Comparar com fonte oficial',
            categoria='Reconciliação',
            score=90,
            evidencia='Motor de reconciliacao cross-source definido para SQL, API, DW e RAG.',
            acao_recomendada='Adicionar adapters reais por fonte oficial.',
        ),
        AriValidationItem(
            codigo='GROUP_BY_GRANULARITY',
            nome='Revisar agregações',
            categoria='Granularidade',
            score=92,
            evidencia='Validação de GROUP BY e granularidade incluida no checklist operacional.',
            acao_recomendada='Exibir dimensoes efetivas no analitico da query.',
        ),
        AriValidationItem(
            codigo='SAMPLE_INSPECTION',
            nome='Analisar amostras manuais',
            categoria='Evidência',
            score=91,
            evidencia='Golden samples previstos para auditoria e reproducibilidade.',
            acao_recomendada='Criar biblioteca de casos canonicos.',
        ),
        AriValidationItem(
            codigo='BUSINESS_RULES',
            nome='Revisar regra de negocio aplicada',
            categoria='Governança funcional',
            score=94,
            evidencia='Regra de negocio passa a ser evidência obrigatoria do resultado analitico.',
            acao_recomendada='Vincular requisito, ADR, teste e query.',
        ),
        AriValidationItem(
            codigo='AI_GROUNDING',
            nome='IA governada com fonte e lineage',
            categoria='IA Auditável',
            status='warn',
            score=89,
            evidencia='Resposta sem fonte ou sem grounding definida como BLOCK.',
            acao_recomendada='Aplicar policy runtime nas respostas de IA.',
        ),
    ]


@router.get('/snapshot')
def obter_snapshot_ari():
    validacoes = _validacoes_base()
    health_score = round(sum(item.score for item in validacoes) / len(validacoes))
    payload = AriRuntimeSnapshot(
        capability='Analytics Runtime Intelligence',
        posicao_estrategica='Plataforma enterprise de inteligencia operacional auditavel',
        health_score=health_score,
        confidence_score=92,
        ai_governance_score=89,
        operational_quality_score=91,
        ambiente='runtime governado',
        atualizado_em=datetime.now(UTC).isoformat(),
        validacoes=validacoes,
        guard_rails=[
            {'regra': 'JOIN explosion', 'acao': 'FAIL'},
            {'regra': 'NULL critico', 'acao': 'FAIL'},
            {'regra': 'Divergencia acima do threshold', 'acao': 'FAIL'},
            {'regra': 'IA sem fonte ou sem grounding', 'acao': 'BLOCK'},
            {'regra': 'Lineage ausente', 'acao': 'WARN'},
            {'regra': 'PII/log sensivel exposto', 'acao': 'FAIL'},
        ],
        figma={
            'status': 'design_operacional_publicado',
            'objetivo': 'retorno visual em tela para ARI, Figma e GitHub',
            'artefato': 'Enterprise Operations Center / Analytics Runtime Intelligence',
        },
        proximas_acoes=[
            'Conectar validadores reais de SQL por adapter.',
            'Persistir historico de health score por execucao.',
            'Adicionar drill-down por query, fonte, regra e incidente.',
            'Sincronizar o artefato Figma com o painel em tela e PR.',
        ],
    )
    return ok(payload.model_dump())
