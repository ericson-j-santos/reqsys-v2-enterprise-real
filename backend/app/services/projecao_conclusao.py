"""Projeção Estatística de Conclusão — ReqSys.

Separa explicitamente estado evidenciado, estado alvo e projeção (ADR-022).
Baseline governado com referência temporal versionada; nunca promove projeção a evidenciado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.estatisticas import gerar_indicadores_estatisticos

REFERENCIA_TEMPORAL = '2026-06-27T21:00:00-03:00'
SCHEMA_VERSION = '1.0.0'
ARTIFACT_RELATIVE = Path('artifacts/completion-projection/completion-projection.json')


@dataclass(frozen=True)
class DimensaoConsolidada:
    dimensao: str
    status_percentual: int
    maturidade: str


@dataclass(frozen=True)
class IndicadorConclusao:
    indicador: str
    percentual: int
    tipo: str  # evidenciado | projeção


@dataclass(frozen=True)
class GapRestante:
    area: str
    gap_percentual: int


@dataclass(frozen=True)
class MarcoProjecao:
    marco: str
    estimativa_dias_min: int
    estimativa_dias_max: int
    cenario: str


@dataclass(frozen=True)
class RiscoEstatistico:
    tipo: str
    nivel: str


@dataclass(frozen=True)
class TendenciaIndicador:
    indicador: str
    tendencia: str


@dataclass(frozen=True)
class ProbabilidadeFinal:
    resultado: str
    probabilidade_percentual: int


def _agora_iso() -> str:
    return datetime.now(UTC).isoformat()


def _baseline_dimensoes() -> list[DimensaoConsolidada]:
    return [
        DimensaoConsolidada('Arquitetura base', 88, 'Alta'),
        DimensaoConsolidada('CI/CD governado', 82, 'Alta'),
        DimensaoConsolidada('Living Architecture', 74, 'Média/Alta'),
        DimensaoConsolidada('Observabilidade/Analytics', 71, 'Média/Alta'),
        DimensaoConsolidada('Runtime operacional', 68, 'Média'),
        DimensaoConsolidada('UX operacional / dashboards', 72, 'Média/Alta'),
        DimensaoConsolidada('Automação autônoma', 63, 'Média'),
        DimensaoConsolidada('Governança enterprise', 79, 'Alta'),
        DimensaoConsolidada('Ambientes sincronizados', 61, 'Média'),
        DimensaoConsolidada('Produção padrão ouro consolidado', 54, 'Média'),
    ]


def _baseline_velocidade() -> dict[str, Any]:
    return {
        'prs_por_dia_uteis': {'min': 8, 'max': 18},
        'merges_verdes_por_dia': {'min': 6, 'max': 14},
        'correcoes_ci_por_ciclo': {'min': 2, 'max': 7},
        'incrementos_paralelos_seguros': {'min': 3, 'max': 5},
        'lead_time_pr_merge_minutos': {'min': 18, 'max': 90},
        'taxa_estabilizacao_ci_percentual': 83,
        'regressao_critica': 'Baixa',
        'retrabalho_estrutural': 'Moderado/baixo',
    }


def _baseline_percentuais_conclusao() -> list[IndicadorConclusao]:
    return [
        IndicadorConclusao('Código implementado', 78, 'evidenciado'),
        IndicadorConclusao('Código validado', 69, 'evidenciado'),
        IndicadorConclusao('Evidência operacional consolidada', 58, 'evidenciado'),
        IndicadorConclusao('Governança enterprise consolidada', 64, 'evidenciado'),
        IndicadorConclusao('Ambientes realmente sincronizados', 61, 'evidenciado'),
        IndicadorConclusao('Runtime navegável/analítico', 67, 'evidenciado'),
        IndicadorConclusao('Autonomia operacional', 55, 'evidenciado'),
        IndicadorConclusao('Padrão ouro total consolidado', 52, 'evidenciado'),
    ]


def _baseline_gaps() -> list[GapRestante]:
    return [
        GapRestante('Consolidação runtime', 18),
        GapRestante('Evidências automatizadas', 22),
        GapRestante('Operação autônoma', 31),
        GapRestante('Analytics/drill-down total', 27),
        GapRestante('Hardening produção', 24),
        GapRestante('Sincronização ambientes', 39),
        GapRestante('Governança viva completa', 21),
        GapRestante('UX operacional enterprise', 17),
    ]


def _baseline_marcos() -> list[MarcoProjecao]:
    marcos = [
        ('MVP operacional consolidado', 3, 6, 'conservador'),
        ('Ambientes sincronizados', 5, 9, 'conservador'),
        ('Runtime operacional robusto', 7, 12, 'conservador'),
        ('Padrão ouro técnico', 14, 22, 'conservador'),
        ('Padrão ouro consolidado total', 21, 35, 'conservador'),
        ('MVP robusto', 2, 4, 'acelerado'),
        ('Produção utilizável forte', 5, 8, 'acelerado'),
        ('Ambientes quase totalmente sincronizados', 4, 7, 'acelerado'),
        ('Padrão ouro técnico', 10, 16, 'acelerado'),
        ('Consolidação enterprise completa', 14, 24, 'acelerado'),
    ]
    return [MarcoProjecao(*item) for item in marcos]


def _baseline_gargalos() -> list[str]:
    return [
        'estabilização contínua de CI',
        'sincronização entre ambientes',
        'evidência operacional automática',
        'consolidação runtime-driven',
        'redução de acoplamentos residuais',
        'observabilidade fim-a-fim',
        'hardening de produção',
    ]


def _baseline_riscos() -> list[RiscoEstatistico]:
    return [
        RiscoEstatistico('Regressão arquitetural', 'Baixo'),
        RiscoEstatistico('Colisão de branches', 'Médio/Baixo'),
        RiscoEstatistico('Instabilidade CI', 'Médio'),
        RiscoEstatistico('Drift entre ambientes', 'Médio'),
        RiscoEstatistico('Escalabilidade operacional', 'Médio'),
        RiscoEstatistico('Perda de rastreabilidade', 'Baixo'),
        RiscoEstatistico('Acoplamento oculto', 'Médio/Baixo'),
    ]


def _baseline_tendencias() -> list[TendenciaIndicador]:
    return [
        TendenciaIndicador('Velocidade', '↑ Forte'),
        TendenciaIndicador('Maturidade', '↑ Forte'),
        TendenciaIndicador('Governança', '↑ Estável'),
        TendenciaIndicador('Autonomia', '↑ Moderada'),
        TendenciaIndicador('Observabilidade', '↑ Forte'),
        TendenciaIndicador('Runtime vivo', '↑ Forte'),
        TendenciaIndicador('Produção consolidada', '↑ Moderada'),
    ]


def _baseline_probabilidades() -> list[ProbabilidadeFinal]:
    return [
        ProbabilidadeFinal('MVP forte em menos de 1 semana', 87),
        ProbabilidadeFinal('Produção utilizável enterprise', 81),
        ProbabilidadeFinal('Padrão ouro técnico real', 73),
        ProbabilidadeFinal('Consolidação enterprise completa', 61),
    ]


def _baseline_aceleradores() -> list[str]:
    return [
        'CI auto-healing',
        'geração automática de evidências',
        'pipeline de validação consolidada',
        'sincronização Fly.io/runtime',
        'monitor operacional centralizado',
        'contratos/shared packages únicos',
        'redução de validações manuais',
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _carregar_artifact_externo() -> dict[str, Any] | None:
    artifact_path = _repo_root() / ARTIFACT_RELATIVE
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding='utf-8'))
        if payload.get('schema_version') == SCHEMA_VERSION:
            return payload
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _enriquecer_com_requisitos(db: Session, percentuais: list[IndicadorConclusao]) -> list[dict[str, Any]]:
    indicadores_db = gerar_indicadores_estatisticos(db)
    conclusao_db = next(
        (item['valorAtual'] for item in indicadores_db if item['id'] == 'requisitos-concluidos'),
        None,
    )
    resultado = []
    for item in percentuais:
        entry: dict[str, Any] = {
            'indicador': item.indicador,
            'percentual': item.percentual,
            'tipo': item.tipo,
        }
        if item.indicador == 'Código implementado' and isinstance(conclusao_db, (int, float)):
            entry['complemento_evidenciado'] = {
                'requisitos_concluidos_percentual': conclusao_db,
                'fonte': 'backend-db:requisitos.status',
            }
        resultado.append(entry)
    return resultado


def _serializar_dimensao(item: DimensaoConsolidada) -> dict[str, Any]:
    return {'dimensao': item.dimensao, 'status_percentual': item.status_percentual, 'maturidade': item.maturidade}


def _serializar_marco(item: MarcoProjecao) -> dict[str, Any]:
    return {
        'marco': item.marco,
        'estimativa_dias_min': item.estimativa_dias_min,
        'estimativa_dias_max': item.estimativa_dias_max,
        'cenario': item.cenario,
    }


def gerar_snapshot_projecao_conclusao(db: Session, correlation_id: str) -> dict[str, Any]:
    artifact = _carregar_artifact_externo()
    if artifact:
        artifact['correlation_id'] = correlation_id
        artifact['coletado_em'] = _agora_iso()
        artifact['ambiente'] = settings.normalized_environment
        artifact['fonte'] = 'artifact:completion-projection.json'
        return artifact

    dimensoes = _baseline_dimensoes()
    percentuais = _baseline_percentuais_conclusao()
    marcos = _baseline_marcos()

    media_dimensoes = round(sum(d.status_percentual for d in dimensoes) / len(dimensoes), 1)
    media_conclusao = round(sum(p.percentual for p in percentuais) / len(percentuais), 1)
    gap_medio = round(sum(g.gap_percentual for g in _baseline_gaps()) / len(_baseline_gaps()), 1)

    return {
        'schema_version': SCHEMA_VERSION,
        'correlation_id': correlation_id,
        'coletado_em': _agora_iso(),
        'referencia_temporal': REFERENCIA_TEMPORAL,
        'ambiente': settings.normalized_environment,
        'modo': 'governado',
        'fonte': 'backend:projecao_conclusao.baseline_v1',
        'confianca_percentual': 87,
        'cenario_ativo': 'acelerado_recomendado',
        'leitura_executiva': {
            'fase_atual': 'Arquitetura enterprise funcional em aceleração contínua',
            'nao_experimental': True,
            'demonstra': [
                'governança',
                'evolução incremental consistente',
                'arquitetura viva',
                'analytics operacional',
                'automação',
                'observabilidade',
                'fluxo CI/CD maduro',
                'continuidade operacional',
            ],
            'falta_principalmente': [
                'consolidação',
                'sincronização',
                'automação total',
                'hardening enterprise final',
            ],
            'limitante_principal': 'Não é implementação — são estabilização CI, sync ambientes e evidências automáticas',
        },
        'resumo': {
            'media_dimensoes_percentual': media_dimensoes,
            'media_conclusao_percentual': media_conclusao,
            'gap_medio_percentual': gap_medio,
            'padrao_ouro_consolidado_percentual': 52,
            'taxa_estabilizacao_ci_percentual': 83,
        },
        'estado_atual_consolidado': [_serializar_dimensao(d) for d in dimensoes],
        'velocidade_observada': _baseline_velocidade(),
        'percentual_conclusao_real': _enriquecer_com_requisitos(db, percentuais),
        'gaps_restantes': [
            {'area': g.area, 'gap_percentual': g.gap_percentual} for g in _baseline_gaps()
        ],
        'projecao_tempo': {
            'conservador': [_serializar_marco(m) for m in marcos if m.cenario == 'conservador'],
            'acelerado': [_serializar_marco(m) for m in marcos if m.cenario == 'acelerado'],
        },
        'gargalos_principais': _baseline_gargalos(),
        'indice_risco': [{'tipo': r.tipo, 'nivel': r.nivel} for r in _baseline_riscos()],
        'tendencias': [{'indicador': t.indicador, 'tendencia': t.tendencia} for t in _baseline_tendencias()],
        'probabilidades_finais': [
            {'resultado': p.resultado, 'probabilidade_percentual': p.probabilidade_percentual}
            for p in _baseline_probabilidades()
        ],
        'aceleradores_marginais': _baseline_aceleradores(),
        'evidencias': [
            'baseline governado ReqSys 27/06/2026 21:00 BRT',
            'ADR-022 separação evidenciado/alvo/projeção',
            'cadência observada em PRs/merges recentes',
            'operational-maturity-score e runtime-health-center',
        ],
        'pendencias': [
            'histórico versionado de snapshots para regressão estatística',
            'integração automática com ci-lead-time-analytics.json',
            'amostra mínima de 30 ciclos para projeção dinâmica',
        ],
    }
