from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

EstadoComponente = Literal['saudavel', 'degradado', 'critico', 'desconhecido']
Severidade = Literal['baixa', 'media', 'alta', 'critica']
TipoRemediacao = Literal[
    'observacao',
    'retry_governado',
    'bloquear_deploy',
    'registrar_incidente',
    'restart_controlado',
    'rollback_seguro',
]
EstadoExecucao = Literal['permitido_dry_run', 'executado', 'bloqueado_por_politica']


class HealthSignal(BaseModel):
    nome: str
    valor: float | int | str | bool | None = None
    estado: EstadoComponente = 'desconhecido'
    limite: str | None = None
    descricao: str | None = None


class RuntimeComponentHealth(BaseModel):
    componente: str
    estado: EstadoComponente
    severidade: Severidade
    score: int = Field(ge=0, le=100)
    sinais: list[HealthSignal] = Field(default_factory=list)
    evidencias: list[str] = Field(default_factory=list)
    recomendacoes: list[str] = Field(default_factory=list)


class RuntimeHealthSnapshot(BaseModel):
    schema_version: str = '1.0.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    score_global: int = Field(ge=0, le=100)
    estado_global: EstadoComponente
    componentes: list[RuntimeComponentHealth]
    bloqueios_operacionais: list[str] = Field(default_factory=list)


class RemediationRequest(BaseModel):
    codigo_acao: str
    componente: str
    tipo: TipoRemediacao
    motivo: str
    dry_run: bool = True


class RemediationDecision(BaseModel):
    correlation_id: str
    avaliado_em: str
    codigo_acao: str
    componente: str
    tipo: TipoRemediacao
    estado: EstadoExecucao
    permitido: bool
    dry_run: bool
    politica_aplicada: str
    razoes: list[str]
    validacoes_obrigatorias: list[str]
    comandos_planejados: list[str] = Field(default_factory=list)
    auditoria: dict = Field(default_factory=dict)


def _classificar_estado_por_score(score: int) -> EstadoComponente:
    if score >= 85:
        return 'saudavel'
    if score >= 65:
        return 'degradado'
    if score >= 1:
        return 'critico'
    return 'desconhecido'


def criar_health_snapshot_base(correlation_id: str, ambiente: str) -> RuntimeHealthSnapshot:
    componentes = [
        RuntimeComponentHealth(
            componente='api_fastapi',
            estado='saudavel',
            severidade='baixa',
            score=90,
            sinais=[HealthSignal(nome='health_endpoint', valor='/health', estado='saudavel')],
            evidencias=['Endpoint /health disponível.', 'Envelope operacional suporta correlation_id.'],
            recomendacoes=['Evoluir para health por dependência externa e latência.'],
        ),
        RuntimeComponentHealth(
            componente='observabilidade',
            estado='degradado',
            severidade='media',
            score=62,
            sinais=[HealthSignal(nome='structured_logging', valor=True, estado='saudavel')],
            evidencias=['Logging básico configurado.', 'Snapshot operacional versionado disponível.'],
            recomendacoes=['Adicionar métricas reais e tracing distribuído.'],
        ),
        RuntimeComponentHealth(
            componente='auto_remediacao_runtime',
            estado='degradado',
            severidade='media',
            score=68,
            sinais=[HealthSignal(nome='executor_governado', valor=True, estado='saudavel')],
            evidencias=['Executor governado implementado em modo dry-run.'],
            recomendacoes=['Persistir incidentes e trilha durável de auditoria.'],
        ),
        RuntimeComponentHealth(
            componente='persistencia_auditoria',
            estado='critico',
            severidade='critica',
            score=45,
            sinais=[HealthSignal(nome='auditoria_persistente', valor=False, estado='critico')],
            evidencias=['Auditoria retornada no contrato da API, ainda sem storage durável.'],
            recomendacoes=['Persistir decisões de remediação.'],
        ),
    ]
    score_global = round(sum(componente.score for componente in componentes) / len(componentes))
    return RuntimeHealthSnapshot(
        correlation_id=correlation_id,
        coletado_em=datetime.now(timezone.utc).isoformat(),
        ambiente=ambiente,
        score_global=score_global,
        estado_global=_classificar_estado_por_score(score_global),
        componentes=componentes,
        bloqueios_operacionais=[
            'execucao_real_bloqueada_no_p0_2',
            'restart_real_bloqueado_sem_auditoria_persistente',
            'rollback_real_bloqueado_sem_plano_de_reversao_validado',
        ],
    )


def avaliar_remediacao(
    request: RemediationRequest,
    health_snapshot: RuntimeHealthSnapshot,
    correlation_id: str,
) -> RemediationDecision:
    componentes = {componente.componente: componente for componente in health_snapshot.componentes}
    componente = componentes.get(request.componente)
    validacoes = ['correlation_id obrigatório', 'registro de auditoria obrigatório', 'limite de execução obrigatório']

    if componente is None:
        return RemediationDecision(
            correlation_id=correlation_id,
            avaliado_em=datetime.now(timezone.utc).isoformat(),
            codigo_acao=request.codigo_acao,
            componente=request.componente,
            tipo=request.tipo,
            estado='bloqueado_por_politica',
            permitido=False,
            dry_run=True,
            politica_aplicada='AOP-RUN-UNKNOWN-COMPONENT-001',
            razoes=['componente não encontrado no health snapshot'],
            validacoes_obrigatorias=validacoes,
            auditoria={'motivo': request.motivo, 'ambiente': health_snapshot.ambiente},
        )

    if request.tipo in {'restart_controlado', 'rollback_seguro'}:
        return RemediationDecision(
            correlation_id=correlation_id,
            avaliado_em=datetime.now(timezone.utc).isoformat(),
            codigo_acao=request.codigo_acao,
            componente=request.componente,
            tipo=request.tipo,
            estado='bloqueado_por_politica',
            permitido=False,
            dry_run=True,
            politica_aplicada='AOP-RUN-SENSITIVE-ACTION-BLOCK-001',
            razoes=['ação sensível permanece bloqueada até existir auditoria persistente e plano validado'],
            validacoes_obrigatorias=[*validacoes, 'auditoria persistente', 'plano validado', 'aprovação humana'],
            auditoria={'motivo': request.motivo, 'estado_componente': componente.estado, 'score_componente': componente.score},
        )

    if request.tipo == 'retry_governado':
        return RemediationDecision(
            correlation_id=correlation_id,
            avaliado_em=datetime.now(timezone.utc).isoformat(),
            codigo_acao=request.codigo_acao,
            componente=request.componente,
            tipo=request.tipo,
            estado='permitido_dry_run',
            permitido=True,
            dry_run=True,
            politica_aplicada='AOP-RUN-RETRY-001',
            razoes=['ação não sensível elegível, mas execução real permanece bloqueada no P0.2'],
            validacoes_obrigatorias=[*validacoes, 'confirmar falha transitória', 'persistir auditoria antes de execução real'],
            comandos_planejados=['registrar_incidente', 'reexecutar_acao_transitoria_com_limite'],
            auditoria={'motivo': request.motivo, 'estado_componente': componente.estado, 'score_componente': componente.score},
        )

    return RemediationDecision(
        correlation_id=correlation_id,
        avaliado_em=datetime.now(timezone.utc).isoformat(),
        codigo_acao=request.codigo_acao,
        componente=request.componente,
        tipo=request.tipo,
        estado='permitido_dry_run',
        permitido=True,
        dry_run=True,
        politica_aplicada='AOP-RUN-GOVERNED-NON-SENSITIVE-001',
        razoes=['ação governada não sensível elegível em dry-run'],
        validacoes_obrigatorias=[*validacoes, 'persistir auditoria antes de execução real'],
        comandos_planejados=[request.tipo],
        auditoria={'motivo': request.motivo, 'estado_componente': componente.estado, 'score_componente': componente.score},
    )
