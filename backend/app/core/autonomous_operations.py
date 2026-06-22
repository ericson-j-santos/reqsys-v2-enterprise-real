from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings

NivelMaturidade = Literal['inicial', 'intermediario', 'intermediario_avancado', 'avancado']
TendenciaOperacional = Literal[
    'crescimento_inicial',
    'crescimento_estruturado',
    'expansao_estruturada',
    'expansao_acelerada',
    'consolidacao_continua',
    'expansao_continua',
]
Severidade = Literal['baixa', 'media', 'alta', 'critica']
EstadoAcao = Literal['observacao', 'recomendado', 'apto_auto_remediacao', 'bloqueado_por_politica']


class IndicadorMaturidade(BaseModel):
    pilar: str
    atual_percentual: int = Field(ge=0, le=100)
    alvo_percentual: int = Field(ge=0, le=100)
    nivel_atual_evidenciado: NivelMaturidade
    tendencia_evidenciada: TendenciaOperacional
    impacto_operacional: Severidade
    evidencias: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    proximas_acoes: list[str] = Field(default_factory=list)

    @property
    def gap_percentual(self) -> int:
        return max(self.alvo_percentual - self.atual_percentual, 0)


class PoliticaAutoRemediacao(BaseModel):
    codigo: str
    descricao: str
    escopo: Literal['ci_cd', 'runtime', 'seguranca', 'observabilidade', 'governanca']
    habilitada: bool
    requer_validacao_humana: bool
    limite_execucoes: int = Field(ge=0)
    severidade_maxima_permitida: Severidade
    acoes_permitidas: list[str]
    bloqueios: list[str] = Field(default_factory=list)


class AcaoAutonoma(BaseModel):
    codigo: str
    titulo: str
    estado: EstadoAcao
    severidade: Severidade
    politica: str
    gatilho: str
    resultado_esperado: str
    validacoes_obrigatorias: list[str]
    auditoria_obrigatoria: bool = True


class ResumoOperacaoAutonoma(BaseModel):
    estado_atual_evidenciado: NivelMaturidade
    score_consolidado: int = Field(ge=0, le=100)
    score_alvo: int = Field(default=95, ge=0, le=100)
    gap_consolidado: int = Field(ge=0, le=100)
    risco_operacional: Severidade
    seguranca_consolidada: bool
    pronto_para_auto_remediacao_total: bool
    tendencia_principal: TendenciaOperacional


class SnapshotOperacaoAutonoma(BaseModel):
    schema_version: str = '1.0.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    resumo: ResumoOperacaoAutonoma
    indicadores: list[IndicadorMaturidade]
    politicas: list[PoliticaAutoRemediacao]
    acoes_autonomas: list[AcaoAutonoma]
    decisoes_governanca: list[str]


def classificar_nivel(score: int) -> NivelMaturidade:
    if score >= 90:
        return 'avancado'
    if score >= 75:
        return 'intermediario_avancado'
    if score >= 50:
        return 'intermediario'
    return 'inicial'


def classificar_risco(score: int, gaps_criticos: int) -> Severidade:
    if gaps_criticos > 0 or score < 55:
        return 'critica'
    if score < 70:
        return 'alta'
    if score < 85:
        return 'media'
    return 'baixa'


def calcular_score_consolidado(indicadores: list[IndicadorMaturidade]) -> int:
    if not indicadores:
        return 0

    pesos = {
        'Operação Autônoma': 25,
        'Observabilidade': 20,
        'Segurança Enterprise': 20,
        'CI/CD Governado': 15,
        'Governança': 10,
        'Runtime Intelligence': 10,
    }
    total_pesos = sum(pesos.get(indicador.pilar, 5) for indicador in indicadores)
    if total_pesos == 0:
        return round(mean(indicador.atual_percentual for indicador in indicadores))

    return round(
        sum(indicador.atual_percentual * pesos.get(indicador.pilar, 5) for indicador in indicadores) / total_pesos
    )


def criar_indicadores_base() -> list[IndicadorMaturidade]:
    return [
        IndicadorMaturidade(
            pilar='Operação Autônoma',
            atual_percentual=43,
            alvo_percentual=95,
            nivel_atual_evidenciado='inicial',
            tendencia_evidenciada='crescimento_estruturado',
            impacto_operacional='critica',
            evidencias=['Monitoramento operacional existe, mas auto-remediação ainda não executa ações reais.'],
            gaps=['Auto-remediação real pendente.', 'Self-healing pendente.', 'Orquestração de recuperação ainda inicial.'],
            proximas_acoes=['Implementar executor governado de remediação.', 'Persistir incidentes e ações executadas.'],
        ),
        IndicadorMaturidade(
            pilar='Observabilidade',
            atual_percentual=54,
            alvo_percentual=95,
            nivel_atual_evidenciado='intermediario',
            tendencia_evidenciada='expansao_estruturada',
            impacto_operacional='alta',
            evidencias=['Endpoint de monitoramento operacional expõe snapshot mínimo com correlation_id.'],
            gaps=['OpenTelemetry end-to-end pendente.', 'Alertas inteligentes pendentes.', 'Dashboards unificados pendentes.'],
            proximas_acoes=['Padronizar métricas operacionais.', 'Conectar telemetria ao OCC.'],
        ),
        IndicadorMaturidade(
            pilar='Segurança Enterprise',
            atual_percentual=61,
            alvo_percentual=95,
            nivel_atual_evidenciado='intermediario',
            tendencia_evidenciada='consolidacao_continua',
            impacto_operacional='alta',
            evidencias=['Gates de produção validam JWT, CORS, Azure AD e login demo.'],
            gaps=['Policy-as-Code completa pendente.', 'Auto-quarentena de ambiente inseguro pendente.'],
            proximas_acoes=['Adicionar policies versionadas para remediação.', 'Bloquear ações autônomas sem auditoria.'],
        ),
        IndicadorMaturidade(
            pilar='CI/CD Governado',
            atual_percentual=66,
            alvo_percentual=95,
            nivel_atual_evidenciado='intermediario',
            tendencia_evidenciada='consolidacao_continua',
            impacto_operacional='alta',
            evidencias=['Workflows e testes existem; estabilidade ainda precisa ser evidenciada em CI verde recorrente.'],
            gaps=['Retry inteligente não centralizado.', 'Quality score contínuo pendente.'],
            proximas_acoes=['Adicionar análise de falhas CI.', 'Versionar quality score por execução.'],
        ),
        IndicadorMaturidade(
            pilar='Governança',
            atual_percentual=72,
            alvo_percentual=95,
            nivel_atual_evidenciado='intermediario',
            tendencia_evidenciada='consolidacao_continua',
            impacto_operacional='media',
            evidencias=['ADRs, documentação e gates existem parcialmente.'],
            gaps=['Governance engine ainda não bloqueia todos os desvios operacionais.'],
            proximas_acoes=['Centralizar decisões de bloqueio.', 'Auditar mudanças de estado de maturidade.'],
        ),
        IndicadorMaturidade(
            pilar='Runtime Intelligence',
            atual_percentual=40,
            alvo_percentual=95,
            nivel_atual_evidenciado='inicial',
            tendencia_evidenciada='crescimento_inicial',
            impacto_operacional='critica',
            evidencias=['Health check básico disponível.'],
            gaps=['Anomaly detection pendente.', 'Runtime analytics pendente.', 'Capacity prediction pendente.'],
            proximas_acoes=['Criar avaliador de health por componente.', 'Coletar métricas de erro, latência e disponibilidade.'],
        ),
    ]


def criar_politicas_base() -> list[PoliticaAutoRemediacao]:
    return [
        PoliticaAutoRemediacao(
            codigo='AOP-CI-RETRY-001',
            descricao='Permite retry controlado para falhas transitórias de CI sem alterar código.',
            escopo='ci_cd',
            habilitada=True,
            requer_validacao_humana=False,
            limite_execucoes=2,
            severidade_maxima_permitida='media',
            acoes_permitidas=['reexecutar_job', 'limpar_cache_ci'],
            bloqueios=['não executar se houver falha de teste funcional determinística'],
        ),
        PoliticaAutoRemediacao(
            codigo='AOP-SEC-QUARANTINE-001',
            descricao='Bloqueia promoção de ambiente quando gate de segurança falha.',
            escopo='seguranca',
            habilitada=True,
            requer_validacao_humana=True,
            limite_execucoes=1,
            severidade_maxima_permitida='critica',
            acoes_permitidas=['bloquear_deploy', 'abrir_incidente', 'registrar_auditoria'],
            bloqueios=['não corrigir segredo automaticamente sem rotação validada'],
        ),
        PoliticaAutoRemediacao(
            codigo='AOP-RUN-HEALTH-001',
            descricao='Define remediação segura para degradação de health em runtime.',
            escopo='runtime',
            habilitada=False,
            requer_validacao_humana=True,
            limite_execucoes=0,
            severidade_maxima_permitida='alta',
            acoes_permitidas=['restart_controlado', 'rollback_seguro', 'failover'],
            bloqueios=['desabilitada até existir health validator por componente'],
        ),
    ]


def criar_acoes_base() -> list[AcaoAutonoma]:
    return [
        AcaoAutonoma(
            codigo='AOP-ACT-001',
            titulo='Retry inteligente de falha transitória em CI',
            estado='apto_auto_remediacao',
            severidade='media',
            politica='AOP-CI-RETRY-001',
            gatilho='timeout, erro de infraestrutura ou cache corrompido',
            resultado_esperado='reduzir reincidência operacional sem mascarar falha funcional',
            validacoes_obrigatorias=['confirmar assinatura transitória', 'registrar correlation_id', 'limitar tentativas'],
        ),
        AcaoAutonoma(
            codigo='AOP-ACT-002',
            titulo='Bloqueio de deploy inseguro',
            estado='apto_auto_remediacao',
            severidade='critica',
            politica='AOP-SEC-QUARANTINE-001',
            gatilho='auth desligada, CORS *, JWT inválido ou secret fraco em produção',
            resultado_esperado='impedir promoção insegura e reduzir impacto de configuração indevida',
            validacoes_obrigatorias=['validar ambiente', 'registrar motivo do bloqueio', 'abrir trilha de auditoria'],
        ),
        AcaoAutonoma(
            codigo='AOP-ACT-003',
            titulo='Restart controlado por health degradado',
            estado='bloqueado_por_politica',
            severidade='alta',
            politica='AOP-RUN-HEALTH-001',
            gatilho='health check degradado por componente',
            resultado_esperado='reduzir MTTR sem intervenção manual',
            validacoes_obrigatorias=['health validator por componente', 'limite de restart', 'rollback disponível'],
        ),
    ]


def gerar_snapshot_operacao_autonoma(correlation_id: str) -> SnapshotOperacaoAutonoma:
    indicadores = criar_indicadores_base()
    politicas = criar_politicas_base()
    acoes = criar_acoes_base()
    score = calcular_score_consolidado(indicadores)
    gaps_criticos = sum(1 for indicador in indicadores if indicador.impacto_operacional == 'critica' and indicador.gap_percentual > 0)

    return SnapshotOperacaoAutonoma(
        correlation_id=correlation_id,
        coletado_em=datetime.now(timezone.utc).isoformat(),
        ambiente=settings.normalized_environment,
        resumo=ResumoOperacaoAutonoma(
            estado_atual_evidenciado=classificar_nivel(score),
            score_consolidado=score,
            gap_consolidado=max(95 - score, 0),
            risco_operacional=classificar_risco(score, gaps_criticos),
            seguranca_consolidada=False,
            pronto_para_auto_remediacao_total=False,
            tendencia_principal='crescimento_estruturado',
        ),
        indicadores=indicadores,
        politicas=politicas,
        acoes_autonomas=acoes,
        decisoes_governanca=[
            'Estado atual não deve ser elevado sem evidência de implementação e validação.',
            'Ações autônomas destrutivas permanecem bloqueadas até existir health validator e auditoria persistente.',
            'Segurança é gate de promoção e pode bloquear deploy antes de qualquer expansão funcional.',
        ],
    )
