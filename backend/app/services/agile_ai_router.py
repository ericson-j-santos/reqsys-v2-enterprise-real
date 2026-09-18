from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.models.agile_runtime import AgileWorkItem


@dataclass(frozen=True)
class AgileAIRoutingRecommendation:
    owner_ai: str
    categoria: str
    labels: list[str]
    branch_sugerida: str
    pipeline_sugerido: str
    prioridade_sugerida: str
    confianca: float
    justificativas: list[str]
    acoes_recomendadas: list[str]


_AGENT_RULES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        'security-ia',
        ('seguranca', 'security', 'lgpd', 'vulnerabilidade', 'jwt', 'token', 'secret', 'permissao', 'auth', 'cors'),
        'seguranca-governanca',
        'security-governance-gates',
    ),
    (
        'devops-ia',
        ('ci', 'cd', 'deploy', 'pipeline', 'github', 'gitlab', 'workflow', 'action', 'fly', 'docker', 'release'),
        'devops-ci-cd',
        'ci-cd-pipeline',
    ),
    (
        'backend-ia',
        ('api', 'endpoint', 'fastapi', 'sqlalchemy', 'schema', 'banco', 'sql', 'servico', 'backend', 'pydantic'),
        'backend-api',
        'backend-ci',
    ),
    (
        'frontend-ia',
        ('frontend', 'tela', 'view', 'vue', 'vite', 'vuetify', 'ux', 'ui', 'kanban', 'dashboard', 'responsivo'),
        'frontend-ux',
        'frontend-ci',
    ),
    (
        'qa-ia',
        ('teste', 'testes', 'pytest', 'coverage', 'qualidade', 'validar', 'evidencia', 'regressao'),
        'qa-validacao',
        'quality-gates',
    ),
    (
        'arquiteto-ia',
        ('arquitetura', 'adr', 'desacoplamento', 'governanca', 'dominio', 'hexagonal', 'runtime'),
        'arquitetura',
        'architecture-review',
    ),
    (
        'analista-requisitos-ia',
        ('requisito', 'story', 'criterio', 'gherkin', 'ambiguo', 'refinamento', 'moscow', 'dor', 'dod'),
        'requisitos-refinamento',
        'requirements-review',
    ),
)

_PRIORITY_WEIGHT = {'P0': 35, 'P1': 25, 'P2': 15, 'P3': 5}


def recomendar_roteamento_multi_ia(item: AgileWorkItem) -> AgileAIRoutingRecommendation:
    texto = _normalizar_texto(
        ' '.join(
            [
                item.tipo or '',
                item.titulo or '',
                item.descricao or '',
                item.criterios_aceite or '',
                item.repositorio or '',
                item.branch or '',
            ]
        )
    )
    regra, hits = _selecionar_regra(texto)
    owner_ai, _, categoria, pipeline = regra
    prioridade = _prioridade_recomendada(item)
    labels = _labels(item, owner_ai, categoria, prioridade)
    confianca = _calcular_confianca(item, hits)
    branch = item.branch or _branch_sugerida(item, owner_ai)

    justificativas = [
        f'Classificacao por categoria operacional: {categoria}.',
        f'IA destino sugerida: {owner_ai}.',
        f'Pipeline recomendado: {pipeline}.',
    ]
    if hits:
        justificativas.append('Termos detectados: ' + ', '.join(sorted(hits)[:8]) + '.')
    if item.score_risco >= 70:
        justificativas.append('Risco alto detectado; manter revisão humana obrigatória antes de merge.')

    return AgileAIRoutingRecommendation(
        owner_ai=owner_ai,
        categoria=categoria,
        labels=labels,
        branch_sugerida=branch,
        pipeline_sugerido=pipeline,
        prioridade_sugerida=prioridade,
        confianca=confianca,
        justificativas=justificativas,
        acoes_recomendadas=_acoes_recomendadas(owner_ai, pipeline, item),
    )


def _selecionar_regra(texto: str) -> tuple[tuple[str, tuple[str, ...], str, str], set[str]]:
    melhor_regra = _AGENT_RULES[-1]
    melhores_hits: set[str] = set()
    for regra in _AGENT_RULES:
        _, keywords, _, _ = regra
        hits = {keyword for keyword in keywords if keyword in texto}
        if len(hits) > len(melhores_hits):
            melhor_regra = regra
            melhores_hits = hits
    return melhor_regra, melhores_hits


def _prioridade_recomendada(item: AgileWorkItem) -> str:
    prioridade_atual = (item.prioridade or 'P2').upper()
    if item.score_risco >= 85 or item.valor_negocio >= 90:
        return 'P0'
    if item.score_risco >= 60 or item.valor_negocio >= 70 or item.pontos >= 8:
        return 'P1'
    if prioridade_atual in _PRIORITY_WEIGHT:
        return prioridade_atual
    return 'P2'


def _labels(item: AgileWorkItem, owner_ai: str, categoria: str, prioridade: str) -> list[str]:
    risco = 'alto' if item.score_risco >= 70 else 'medio' if item.score_risco >= 35 else 'baixo'
    return sorted(
        {
            'agile-runtime',
            'multi-ia-router',
            f'ai:{owner_ai}',
            f'categoria:{categoria}',
            f'prioridade:{prioridade.lower()}',
            f'risco:{risco}',
            f'tipo:{(item.tipo or "work-item").replace("_", "-")}',
        }
    )


def _branch_sugerida(item: AgileWorkItem, owner_ai: str) -> str:
    prefixo = {
        'security-ia': 'security',
        'devops-ia': 'ci',
        'backend-ia': 'backend',
        'frontend-ia': 'frontend',
        'qa-ia': 'test',
        'arquiteto-ia': 'arch',
        'analista-requisitos-ia': 'req',
    }.get(owner_ai, 'agile')
    codigo = _slug(item.codigo or f'agi-{item.id}')
    titulo = _slug(item.titulo or 'work-item')[:48]
    return f'feature/{prefixo}/{codigo}-{titulo}'.strip('-')


def _calcular_confianca(item: AgileWorkItem, hits: Iterable[str]) -> float:
    hit_count = len(set(hits))
    base = 0.45 + min(hit_count, 6) * 0.07
    if item.tipo:
        base += 0.04
    if item.criterios_aceite:
        base += 0.05
    if item.score_risco >= 70:
        base -= 0.04
    return round(max(0.35, min(base, 0.95)), 2)


def _acoes_recomendadas(owner_ai: str, pipeline: str, item: AgileWorkItem) -> list[str]:
    acoes = [
        'Registrar owner IA sugerido no work item.',
        'Aplicar labels sugeridas no issue/PR/MR quando houver integração externa ativa.',
        'Criar ou reaproveitar branch sugerida antes da execução técnica.',
        f'Usar pipeline recomendado: {pipeline}.',
    ]
    if owner_ai in {'security-ia', 'devops-ia'} or item.score_risco >= 70:
        acoes.append('Exigir revisão humana antes de merge/deploy.')
    if owner_ai == 'qa-ia':
        acoes.append('Adicionar evidência de teste automatizado ao Agile Runtime.')
    return acoes


def _normalizar_texto(valor: str) -> str:
    return valor.lower().replace('ç', 'c').replace('ã', 'a').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')


def _slug(valor: str) -> str:
    normalizado = _normalizar_texto(valor)
    normalizado = re.sub(r'[^a-z0-9]+', '-', normalizado)
    return re.sub(r'-+', '-', normalizado).strip('-') or 'work-item'
