from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

AgileWorkItemTipo = Literal['epic', 'feature', 'story', 'task', 'bug', 'spike', 'risk', 'tech_debt', 'adr']
AgilePrioridade = Literal['P0', 'P1', 'P2', 'P3']
AgileWorkflowStatus = Literal[
    'novo',
    'refinando',
    'pronto_para_sprint',
    'planejado',
    'em_execucao',
    'em_revisao',
    'em_ci',
    'homologacao',
    'evidenciado',
    'producao',
    'monitorado',
    'concluido',
    'bloqueado',
    'reprovado',
    'cancelado',
    'reaberto',
]


class AgileSprintCriar(BaseModel):
    nome: str = Field(min_length=3, max_length=160)
    objetivo: str = Field(min_length=10)
    data_inicio: date
    data_fim: date
    capacidade_pontos: int = Field(default=0, ge=0)
    pontos_comprometidos: int = Field(default=0, ge=0)


class AgileSprintOut(AgileSprintCriar):
    id: int
    codigo: str
    pontos_concluidos: int
    status: str
    criado_em: datetime

    class Config:
        from_attributes = True


class AgileWorkItemCriar(BaseModel):
    tipo: AgileWorkItemTipo = 'story'
    titulo: str = Field(min_length=5, max_length=220)
    descricao: str = Field(min_length=10)
    prioridade: AgilePrioridade = 'P2'
    pontos: int = Field(default=0, ge=0, le=100)
    valor_negocio: int = Field(default=0, ge=0, le=100)
    score_risco: int = Field(default=0, ge=0, le=100)
    owner_ai: str | None = Field(default=None, max_length=80)
    requisito_id: int | None = None
    sprint_id: int | None = None
    parent_id: int | None = None
    criterios_aceite: str | None = None
    repositorio: str | None = Field(default=None, max_length=220)
    branch: str | None = Field(default=None, max_length=160)


class AgileWorkItemOut(AgileWorkItemCriar):
    id: int
    codigo: str
    status: str
    change_provider: str | None = None
    change_id: str | None = None
    change_url: str | None = None
    ci_provider: str | None = None
    ci_run_id: str | None = None
    ci_status: str
    ci_url: str | None = None
    ambiente_deploy: str
    deploy_status: str
    deploy_url: str | None = None
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


class AgileWorkflowTransicao(BaseModel):
    status: AgileWorkflowStatus
    motivo: str | None = Field(default=None, max_length=500)


class AgileTraceabilityAtualizar(BaseModel):
    repositorio: str | None = Field(default=None, max_length=220)
    branch: str | None = Field(default=None, max_length=160)
    change_provider: Literal['github', 'gitlab'] | None = None
    change_id: str | None = Field(default=None, max_length=80)
    change_url: str | None = None
    ci_provider: Literal['github_actions', 'gitlab_ci', 'other'] | None = None
    ci_run_id: str | None = Field(default=None, max_length=120)
    ci_status: Literal['pending', 'running', 'success', 'failed', 'cancelled', 'unknown'] = 'unknown'
    ci_url: str | None = None
    ambiente_deploy: Literal['dev', 'test', 'homolog', 'prod', 'none'] = 'none'
    deploy_status: Literal['not_started', 'deployed', 'failed', 'rolled_back', 'unknown'] = 'not_started'
    deploy_url: str | None = None


class AgileEvidenceCriar(BaseModel):
    tipo: Literal['pr', 'mr', 'ci', 'deploy', 'teste', 'homologacao', 'monitoramento', 'auditoria', 'outro']
    titulo: str = Field(min_length=5, max_length=220)
    url: str | None = None
    status: str = Field(default='registrada', max_length=30)
    observacao: str | None = None
    criado_por: str | None = Field(default=None, max_length=120)


class AgileEvidenceOut(AgileEvidenceCriar):
    id: int
    work_item_id: int
    correlation_id: str | None = None
    criado_em: datetime

    class Config:
        from_attributes = True


class AgileRuntimeResumo(BaseModel):
    total_itens: int
    total_sprints: int
    total_evidencias: int
    itens_concluidos: int
    itens_em_ci: int
    itens_bloqueados: int
    conclusao_percentual: float
    ci_success_percentual: float


AgileLaunchpadAmbiente = Literal['dev', 'test', 'homolog', 'prod']


class AgileGithubLaunchpadLinks(BaseModel):
    branch: str
    criar_branch: str
    novo_pr: str
    actions: str
    app_ambiente: str | None = None
    repositorio: str
    change_request: str | None = None
    ci: str | None = None
    deploy: str | None = None


class AgileGithubLaunchpadOut(BaseModel):
    work_item_id: int
    work_item_codigo: str
    requisito_codigo: str | None = None
    ambiente: AgileLaunchpadAmbiente
    ambiente_branch_inferido: str | None = None
    repositorio: str
    branch_trabalho: str
    branch_base: str
    branch_existe: bool | None = None
    links: AgileGithubLaunchpadLinks
    acoes_disponiveis: list[str]
    somente_leitura: bool = False
    increment_gate: dict | None = None
    mensagem_commit_sugerida: str
    notas: list[str] = Field(default_factory=list)


class IncrementGateResumo(BaseModel):
    permitido: bool
    motivo: str
    detalhe: str


class GithubBranchCriarIn(BaseModel):
    ambiente: str = 'dev'
    criar_se_ausente: bool = True
    aplicar_branch_no_item: bool = True


class GithubBranchCriarOut(BaseModel):
    criada: bool
    branch: str
    repositorio: str
    branch_base: str
    branch_existe: bool
    motivo: str
    increment_gate: IncrementGateResumo
    links: AgileGithubLaunchpadLinks


class AgileAIRoutingRecommendationOut(BaseModel):
    work_item_id: int
    work_item_codigo: str
    owner_ai: str
    categoria: str
    labels: list[str]
    branch_sugerida: str
    pipeline_sugerido: str
    prioridade_sugerida: AgilePrioridade
    confianca: float = Field(ge=0.0, le=1.0)
    justificativas: list[str]
    acoes_recomendadas: list[str]
    modo: Literal['preview', 'aplicado'] = 'preview'
