from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?;])\s+|\n+')
_TECHNICAL_TERMS = (
    'api', 'endpoint', 'backend', 'frontend', 'database', 'banco', 'sql', 'fila',
    'worker', 'cache', 'deploy', 'ci', 'cd', 'oauth', 'jwt', 'rbac', 'log',
    'observabilidade', 'telemetria', 'integração', 'integracao', 'webhook',
)
_BUSINESS_TERMS = (
    'usuário', 'usuario', 'cliente', 'negócio', 'negocio', 'processo', 'valor',
    'benefício', 'beneficio', 'resultado', 'aprovação', 'aprovacao', 'gestor',
    'analista', 'prazo', 'custo', 'receita', 'produtividade', 'compliance',
)


@dataclass(frozen=True)
class AgileProjectDemand:
    titulo: str
    descricao: str
    objetivo: str | None = None
    publico_alvo: str | None = None
    owner: str | None = None
    prioridade: str = 'media'
    correlation_id: str | None = None


def _sentences(text: str) -> list[str]:
    return [item.strip(' -\t') for item in _SENTENCE_SPLIT.split(text.strip()) if item.strip(' -\t')]


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = text.casefold()
    return any(
        re.search(rf'(?<!\w){re.escape(term.casefold())}(?!\w)', normalized)
        for term in terms
    )


def _stable_id(prefix: str, demand: AgileProjectDemand) -> str:
    raw = f'{demand.titulo}|{demand.descricao}|{demand.objetivo or ""}'.encode('utf-8')
    return f'{prefix}-{hashlib.sha256(raw).hexdigest()[:10]}'


def _extract_requirements(demand: AgileProjectDemand) -> tuple[list[str], list[str]]:
    business: list[str] = []
    technical: list[str] = []

    for sentence in _sentences(demand.descricao):
        is_technical = _contains_any(sentence, _TECHNICAL_TERMS)
        is_business = _contains_any(sentence, _BUSINESS_TERMS)
        if is_technical:
            technical.append(sentence)
        if is_business or not is_technical:
            business.append(sentence)

    if demand.objetivo and demand.objetivo not in business:
        business.insert(0, demand.objetivo.strip())

    return business, technical


def _acceptance_criteria(business: list[str], technical: list[str]) -> list[str]:
    criteria = [f'Dado que a demanda foi refinada, quando {item.rstrip(".")}, então a evidência deve ser registrada.' for item in business[:3]]
    criteria.extend(
        f'Dado que a solução está disponível, quando {item.rstrip(".")}, então a validação técnica deve passar sem regressão.'
        for item in technical[:3]
    )
    return criteria or ['Dado que o escopo foi aprovado, quando a entrega for validada, então o aceite deve ficar auditável.']


def gerar_pacote_agil(demand: AgileProjectDemand) -> dict:
    business, technical = _extract_requirements(demand)
    target_user = demand.publico_alvo or 'usuário do processo'
    objective = demand.objetivo or (business[0] if business else demand.titulo)
    owner = demand.owner or 'nao_definido'
    gaps = []
    if demand.owner is None:
        gaps.append('owner_nao_definido')
    if demand.publico_alvo is None:
        gaps.append('publico_alvo_nao_definido')
    if not technical:
        gaps.append('requisitos_tecnicos_insuficientes')

    story = f'Como {target_user}, quero {demand.titulo.casefold()} para {objective.rstrip(".").casefold()}.'
    criteria = _acceptance_criteria(business, technical)
    estimate = min(13, max(2, len(criteria) + len(technical)))

    return {
        'schema_version': '1.0.0',
        'package_id': _stable_id('agile', demand),
        'correlation_id': demand.correlation_id,
        'project': {
            'title': demand.titulo,
            'objective': objective,
            'owner': owner,
            'target_audience': target_user,
            'priority': demand.prioridade,
        },
        'business': {
            'requirements': business,
            'expected_value': objective,
            'success_metrics': [
                'taxa_de_aceite_funcional',
                'lead_time_da_demanda',
                'retrabalho_pos_homologacao',
            ],
        },
        'technical': {
            'requirements': technical,
            'quality_attributes': [
                'seguranca',
                'observabilidade',
                'testabilidade',
                'rastreabilidade',
            ],
            'mandatory_evidence': [
                'testes_automatizados',
                'evidencia_ci',
                'validacao_homologacao',
            ],
        },
        'scrum': {
            'epic': demand.titulo,
            'user_story': story,
            'acceptance_criteria': criteria,
            'definition_of_ready': [
                'owner definido',
                'valor negocial explícito',
                'critérios de aceite verificáveis',
                'dependências e riscos identificados',
            ],
            'definition_of_done': [
                'critérios de aceite aprovados',
                'testes automatizados verdes',
                'evidência técnica e funcional anexada',
                'documentação e rastreabilidade atualizadas',
            ],
            'story_points_suggested': estimate,
            'sprint_recommendation': 'proxima_sprint' if not gaps else 'refinamento',
        },
        'governance': {
            'human_approval_required': True,
            'gaps': gaps,
            'risk_level': 'medio' if gaps else 'baixo',
            'next_action': 'resolver_gaps_de_refinamento' if gaps else 'priorizar_no_backlog',
        },
    }
