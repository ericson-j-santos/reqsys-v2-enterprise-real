from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.agile_runtime import AgileWorkItem
from app.services.agile_ai_router import recomendar_roteamento_multi_ia

GitProvider = Literal['github', 'gitlab']


@dataclass(frozen=True)
class GitProviderGovernedPlan:
    provider: GitProvider
    repository: str
    issue_title: str
    issue_body: str
    labels: list[str]
    branch_name: str
    pipeline_name: str
    change_kind: Literal['issue', 'branch', 'merge_request', 'pull_request']
    governance_mode: Literal['plan_only', 'manual_approval_required']
    risk_level: Literal['baixo', 'medio', 'alto']
    requires_human_approval: bool
    evidence_title: str
    evidence_summary: str
    next_actions: list[str]


def gerar_plano_git_governado(item: AgileWorkItem, provider: GitProvider = 'github') -> GitProviderGovernedPlan:
    routing = recomendar_roteamento_multi_ia(item)
    repository = item.repositorio or 'ericson-j-santos/reqsys-v2-enterprise-real'
    risk_level = _risk_level(item.score_risco)
    requires_human_approval = risk_level == 'alto' or routing.owner_ai in {'security-ia', 'devops-ia'}
    change_kind = 'pull_request' if provider == 'github' else 'merge_request'

    issue_title = f'[{routing.prioridade_sugerida}] {item.codigo} — {item.titulo}'
    issue_body = _issue_body(item, routing.owner_ai, routing.pipeline_sugerido, routing.confianca, provider)
    governance_mode = 'manual_approval_required' if requires_human_approval else 'plan_only'

    return GitProviderGovernedPlan(
        provider=provider,
        repository=repository,
        issue_title=issue_title,
        issue_body=issue_body,
        labels=routing.labels,
        branch_name=routing.branch_sugerida,
        pipeline_name=routing.pipeline_sugerido,
        change_kind=change_kind,
        governance_mode=governance_mode,
        risk_level=risk_level,
        requires_human_approval=requires_human_approval,
        evidence_title=f'Plano {provider.upper()} governado gerado',
        evidence_summary=(
            f'provider={provider}; repository={repository}; owner_ai={routing.owner_ai}; '
            f'branch={routing.branch_sugerida}; pipeline={routing.pipeline_sugerido}; '
            f'risk={risk_level}; approval={requires_human_approval}'
        ),
        next_actions=_next_actions(provider, requires_human_approval),
    )


def _risk_level(score_risco: int) -> Literal['baixo', 'medio', 'alto']:
    if score_risco >= 70:
        return 'alto'
    if score_risco >= 35:
        return 'medio'
    return 'baixo'


def _issue_body(item: AgileWorkItem, owner_ai: str, pipeline: str, confidence: float, provider: GitProvider) -> str:
    provider_label = 'GitHub' if provider == 'github' else 'GitLab'
    return '\n'.join(
        [
            '## ReqSys Agile Runtime — plano governado',
            '',
            f'- Work item: `{item.codigo}`',
            f'- Tipo: `{item.tipo}`',
            f'- Prioridade atual: `{item.prioridade}`',
            f'- Owner IA sugerido: `{owner_ai}`',
            f'- Pipeline sugerido: `{pipeline}`',
            f'- Confiança do roteamento: `{confidence}`',
            f'- Provider alvo: `{provider_label}`',
            '',
            '## Descrição',
            item.descricao or 'Sem descrição informada.',
            '',
            '## Critérios de aceite',
            item.criterios_aceite or 'Critérios de aceite ainda não informados.',
            '',
            '## Governança',
            '- Este plano não executa ação externa automaticamente.',
            '- Criar issue/branch/PR/MR requer adaptador autenticado e aprovação conforme risco.',
            '- Registrar evidência no Agile Runtime antes de avançar workflow.',
        ]
    )


def _next_actions(provider: GitProvider, requires_human_approval: bool) -> list[str]:
    target = 'GitHub' if provider == 'github' else 'GitLab'
    actions = [
        f'Revisar plano antes de materializar no {target}.',
        'Criar issue usando título, corpo e labels sugeridas.',
        'Criar branch sugerida somente após aprovação do plano.',
        'Associar PR/MR ao work item quando existir alteração de código.',
        'Registrar URL da issue/PR/MR e CI como evidência no Agile Runtime.',
    ]
    if requires_human_approval:
        actions.insert(1, 'Obter aprovação humana obrigatória antes de criar branch, PR/MR ou deploy.')
    return actions
