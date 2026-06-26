from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


@dataclass(frozen=True)
class CoordinatorRule:
    coordinator_id: str
    nome: str
    tema: str
    destino_operacional: str
    backlog_destino: str
    pipeline_sugerido: str
    labels: tuple[str, ...]
    palavras_chave: tuple[str, ...]
    automacoes: tuple[str, ...]
    riscos_padrao: tuple[str, ...]


@dataclass(frozen=True)
class OrchestratorDemand:
    titulo: str
    descricao: str = ''
    origem: str = 'chat'
    prioridade_informada: str | None = None
    ambiente: str | None = None
    correlation_id: str | None = None


COORDINATORS: tuple[CoordinatorRule, ...] = (
    CoordinatorRule(
        coordinator_id='reqsys-runtime-coordinator',
        nome='Coordenador IA Runtime/Fly.io',
        tema='runtime',
        destino_operacional='runtime_queue',
        backlog_destino='Backlog Runtime e Deploy Governado',
        pipeline_sugerido='runtime-health-validator',
        labels=('runtime', 'flyio', 'deploy', 'observabilidade'),
        palavras_chave=('runtime', 'fly', 'fly.io', 'deploy', 'health', 'readiness', 'liveness', 'ambiente', 'homologacao', 'produção', 'producao', 'prod'),
        automacoes=('validar runtime health', 'verificar drift de ambiente', 'gerar evidencia pos-deploy'),
        riscos_padrao=('drift_ambiente', 'deploy_sem_evidencia', 'secret_divergente'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-ci-coordinator',
        nome='Coordenador IA CI/CD',
        tema='ci_cd',
        destino_operacional='ci_queue',
        backlog_destino='Backlog CI/CD e Evidence Gate',
        pipeline_sugerido='ci-router-result',
        labels=('ci', 'github-actions', 'evidence-gate'),
        palavras_chave=('ci', 'pipeline', 'workflow', 'actions', 'pytest', 'coverage', 'lint', 'gate', 'merge', 'pr', 'rerun'),
        automacoes=('classificar falha de CI', 'sugerir menor correcao', 'registrar evidencia de rerun'),
        riscos_padrao=('ci_instavel', 'merge_sem_gate', 'evidencia_ausente'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-agile-coordinator',
        nome='Coordenador IA Agile/Scrum',
        tema='agile_scrum',
        destino_operacional='agile_queue',
        backlog_destino='Backlog Agile Runtime',
        pipeline_sugerido='agile-runtime-router',
        labels=('agile', 'scrum', 'backlog', 'sprint'),
        palavras_chave=('agile', 'ágil', 'scrum', 'sprint', 'kanban', 'backlog', 'story', 'historia', 'história', 'cerimonia', 'cerimônia'),
        automacoes=('classificar work item', 'sugerir sprint', 'atualizar rastreabilidade agile'),
        riscos_padrao=('escopo_sem_owner', 'prioridade_ambigua', 'lead_time_sem_metrica'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-govbi-coordinator',
        nome='Coordenador IA GovBI',
        tema='govbi',
        destino_operacional='govbi_queue',
        backlog_destino='Backlog GovBI e Analytics',
        pipeline_sugerido='govbi-analytics-validator',
        labels=('govbi', 'analytics', 'power-bi', 'sql'),
        palavras_chave=('govbi', 'bi', 'power bi', 'dashboard', 'analytics', 'indicador', 'kpi', 'sql', 'databricks', 'relatorio', 'relatório'),
        automacoes=('mapear indicador', 'sugerir camada analitica', 'registrar contrato de metrica'),
        riscos_padrao=('metrica_sem_definicao', 'fonte_sem_linhagem', 'consulta_sem_guardrail'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-ai-coordinator',
        nome='Coordenador IA/RAG/Agentes',
        tema='ia_rag_agents',
        destino_operacional='ai_queue',
        backlog_destino='Backlog IA, RAG e Agentes',
        pipeline_sugerido='ai-governance-gate',
        labels=('ia', 'rag', 'agents', 'governanca-ia'),
        palavras_chave=('ia', 'ai', 'rag', 'agente', 'agent', 'llamaindex', 'ollama', 'embedding', 'prompt', 'copilot', 'multiagente'),
        automacoes=('avaliar politica de IA', 'sugerir guardrails', 'registrar decisao de agente'),
        riscos_padrao=('acao_autonoma_sem_aprovacao', 'prompt_sem_rastreabilidade', 'fonte_rag_sem_confianca'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-security-coordinator',
        nome='Coordenador IA Segurança/Governança',
        tema='seguranca_governanca',
        destino_operacional='security_queue',
        backlog_destino='Backlog Segurança e Governança',
        pipeline_sugerido='security-governance-gate',
        labels=('security', 'governanca', 'lgpd', 'rbac'),
        palavras_chave=('segurança', 'seguranca', 'security', 'lgpd', 'jwt', 'rbac', 'secret', 'token', 'cors', 'auditoria', 'correlation'),
        automacoes=('avaliar risco', 'bloquear producao se necessario', 'registrar evidencia de governanca'),
        riscos_padrao=('segredo_exposto', 'permissao_excessiva', 'auditoria_insuficiente'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-ux-coordinator',
        nome='Coordenador IA UX/UI',
        tema='ux_ui',
        destino_operacional='ux_queue',
        backlog_destino='Backlog UX, Responsividade e Drill-down',
        pipeline_sugerido='frontend-responsive-e2e',
        labels=('ux', 'ui', 'responsividade', 'drill-down'),
        palavras_chave=('ux', 'ui', 'layout', 'responsivo', 'responsividade', 'tela', 'aba', 'drill', 'drill-down', 'figma', 'dashboard visual'),
        automacoes=('sugerir melhoria responsiva', 'mapear drill-down', 'validar e2e visual'),
        riscos_padrao=('ux_inconsistente', 'drilldown_sem_estado', 'responsividade_nao_validada'),
    ),
    CoordinatorRule(
        coordinator_id='reqsys-architecture-coordinator',
        nome='Coordenador IA Arquitetura Viva',
        tema='arquitetura',
        destino_operacional='architecture_queue',
        backlog_destino='Backlog Arquitetura Viva e ADR',
        pipeline_sugerido='living-architecture-validator',
        labels=('arquitetura', 'adr', 'living-architecture'),
        palavras_chave=('arquitetura', 'adr', 'diagrama', 'living architecture', 'arquitetura viva', 'hexagonal', 'dominio', 'domínio', 'camada'),
        automacoes=('sugerir ADR', 'atualizar mapa arquitetural', 'validar rastreabilidade tecnica'),
        riscos_padrao=('decisao_sem_adr', 'acoplamento_excessivo', 'documentacao_desatualizada'),
    ),
)

DEFAULT_COORDINATOR = CoordinatorRule(
    coordinator_id='reqsys-intake-coordinator',
    nome='Coordenador IA Intake Central',
    tema='intake',
    destino_operacional='intake_queue',
    backlog_destino='Backlog Intake e Refinamento',
    pipeline_sugerido='intake-refinement-gate',
    labels=('intake', 'triagem', 'refinamento'),
    palavras_chave=(),
    automacoes=('refinar escopo', 'solicitar evidencias minimas', 'classificar tema posteriormente'),
    riscos_padrao=('tema_ambigui', 'escopo_insuficiente'),
)


def _normalizar_texto(valor: str) -> str:
    return valor.lower().strip()


def _score_rule(texto: str, rule: CoordinatorRule) -> int:
    return sum(1 for palavra in rule.palavras_chave if palavra in texto)


def _prioridade(score: int, demanda: OrchestratorDemand) -> str:
    if demanda.prioridade_informada:
        return demanda.prioridade_informada
    if score >= 3:
        return 'alta'
    if score == 2:
        return 'media'
    return 'normal'


def _confianca(score: int) -> float:
    if score <= 0:
        return 0.45
    return min(0.96, 0.58 + (score * 0.1))


def listar_coordenadores() -> list[dict]:
    return [
        {
            'coordinator_id': rule.coordinator_id,
            'nome': rule.nome,
            'tema': rule.tema,
            'destino_operacional': rule.destino_operacional,
            'backlog_destino': rule.backlog_destino,
            'pipeline_sugerido': rule.pipeline_sugerido,
            'labels': list(rule.labels),
            'automacoes': list(rule.automacoes),
        }
        for rule in COORDINATORS
    ]


def classificar_demanda(demanda: OrchestratorDemand) -> dict:
    texto = _normalizar_texto(f'{demanda.titulo} {demanda.descricao}')
    ranked: list[tuple[int, CoordinatorRule]] = sorted(
        ((_score_rule(texto, rule), rule) for rule in COORDINATORS),
        key=lambda item: item[0],
        reverse=True,
    )
    score, rule = ranked[0]
    if score == 0:
        rule = DEFAULT_COORDINATOR

    confianca = _confianca(score)
    prioridade = _prioridade(score, demanda)
    agora = datetime.now(UTC).isoformat()
    labels = list(rule.labels)
    if demanda.ambiente:
        labels.append(f'ambiente:{demanda.ambiente}')
    if prioridade in ('alta', 'critica', 'crítica'):
        labels.append('prioridade-alta')

    return {
        'schema_version': '1.0.0',
        'classified_at': agora,
        'correlation_id': demanda.correlation_id,
        'origem': demanda.origem,
        'tema': rule.tema,
        'coordinator': {
            'id': rule.coordinator_id,
            'nome': rule.nome,
            'destino_operacional': rule.destino_operacional,
            'backlog_destino': rule.backlog_destino,
        },
        'prioridade_sugerida': prioridade,
        'ambiente': demanda.ambiente or 'nao_informado',
        'confianca': round(confianca, 2),
        'score': score,
        'labels': labels,
        'pipeline_sugerido': rule.pipeline_sugerido,
        'automacoes_recomendadas': list(rule.automacoes),
        'riscos_iniciais': list(rule.riscos_padrao),
        'governanca': {
            'modo_execucao': 'assistido',
            'requer_aprovacao_humana': True,
            'gera_evidencia': True,
            'permite_acao_destrutiva': False,
        },
        'proximo_passo': _proximo_passo(rule, score),
    }


def classificar_lote(demandas: Iterable[OrchestratorDemand]) -> dict:
    rotas = [classificar_demanda(demanda) for demanda in demandas]
    por_tema: dict[str, int] = {}
    for rota in rotas:
        por_tema[rota['tema']] = por_tema.get(rota['tema'], 0) + 1
    return {
        'schema_version': '1.0.0',
        'total': len(rotas),
        'por_tema': por_tema,
        'rotas': rotas,
    }


def _proximo_passo(rule: CoordinatorRule, score: int) -> str:
    if rule == DEFAULT_COORDINATOR or score == 0:
        return 'Refinar demanda no intake central antes de automatizar execução.'
    return f'Encaminhar para {rule.nome} e executar automação assistida: {rule.automacoes[0]}.'
