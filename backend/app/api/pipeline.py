from time import time
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.services.github_redmine import (
    IntegracaoError,
    fetch_github_issues,
    github_redmine_import_enabled,
    publish_issues_to_redmine,
)

router = APIRouter(tags=['Pipeline'])

class SolicitacaoIn(BaseModel):
    origem: str
    titulo: str = Field(min_length=5)
    descricao: str = Field(min_length=20)
    solicitante: str
    area: str
    sistema: str
    modulo: str | None = None
    urgencia: str = 'media'
    id_externo: str | None = None
    impacto_regulatorio: bool = False

class ValidacaoIn(BaseModel):
    titulo: str | None = None
    descricao: str | None = None
    requisitos_funcionais: list[str] = []
    criterios_aceite: list[dict] = []


class GitHubIssuesIn(BaseModel):
    repo: str
    state: str = 'open'
    limit: int = Field(default=20, ge=1, le=100)
    labels: list[str] = Field(default_factory=list)


class PublicarRedmineIn(BaseModel):
    use_github_import: bool = False
    github_repo: str | None = None
    github_state: str = 'open'
    github_limit: int = Field(default=20, ge=1, le=100)
    github_labels: list[str] = Field(default_factory=list)
    issue_numbers: list[int] = Field(default_factory=list)
    redmine_project_id: int | None = None
    tracker_id: int | None = None
    priority_id: int | None = None


def inferir_rfs(descricao: str | None) -> list[str]:
    texto = (descricao or '').lower()
    rfs: list[str] = []
    if 'cpf' in texto or 'cnpj' in texto:
        rfs.append('O sistema deve permitir pesquisa por CPF ou CNPJ.')
    if 'consult' in texto or 'verific' in texto:
        rfs.append('Consultar registros antes de criar novo cadastro.')
    if 'cadastro' in texto or 'pre-cadastro' in texto:
        rfs.append('Permitir continuidade do fluxo com edição controlada.')
    return rfs

@router.post('/v1/solicitacoes')
def criar_solicitacao(payload: SolicitacaoIn, x_correlation_id: str | None = Header(default=None)):
    codigo = f"SOL-{str(int(time()))[-8:]}"
    return ok({'id': 1, 'codigo': codigo, 'status': 'recebido'}, x_correlation_id)

@router.post('/v1/requisitos/validar')
def validar_requisito(payload: ValidacaoIn, x_correlation_id: str | None = Header(default=None)):
    texto = f"{payload.titulo or ''} {payload.descricao or ''}".lower()
    ambiguos = [t for t in ['rápido', 'melhor', 'simples', 'fácil', 'intuitivo', 'otimizado'] if t in texto]
    alertas: list[str] = []
    if not payload.requisitos_funcionais:
        alertas.append('Nenhum requisito funcional identificado.')
    if not payload.criterios_aceite:
        alertas.append('Nenhum critério de aceite informado.')
    for termo in ambiguos:
        alertas.append(f"Termo ambíguo detectado: '{termo}'")
    return ok({'aprovado_para_triagem': len(alertas) == 0, 'alertas': alertas}, x_correlation_id)

@router.post('/v1/requisitos/estruturar/{requisito_id}')
def estruturar_requisito(requisito_id: int, payload: SolicitacaoIn, x_correlation_id: str | None = Header(default=None)):
    codigo = f"REQ-{str(int(time()))[-8:]}"
    return ok({
        'requisito_id': requisito_id,
        'codigo_requisito': codigo,
        'tipo': 'funcional',
        'prioridade': payload.urgencia or 'media',
        'requisitos_funcionais': inferir_rfs(payload.descricao),
        'requisitos_nao_funcionais': ['Registrar correlation_id.', 'Acesso respeita perfil do usuário.', 'Resposta ≤ 2s (p95).'],
        'regras_negocio': [{'codigo': 'RN-001', 'descricao': 'Não permitir cadastro ativo duplicado.'}],
        'criterios_aceite': [
            {'ordem': 1, 'descricao': 'Identificador existente → dados exibidos.'},
            {'ordem': 2, 'descricao': 'Identificador inexistente → permitir novo cadastro.'},
        ],
        'alertas_validacao': [],
    }, x_correlation_id)


@router.post('/v1/integracoes/github/issues')
def listar_issues_github(payload: GitHubIssuesIn, x_correlation_id: str | None = Header(default=None)):
    if not github_redmine_import_enabled():
        raise HTTPException(status_code=409, detail='Integração GitHub→Redmine desabilitada por feature flag.')

    try:
        issues = fetch_github_issues(
            repo=payload.repo,
            state=payload.state,
            limit=payload.limit,
            labels=payload.labels,
        )
    except IntegracaoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ok(
        {
            'repo': payload.repo,
            'state': payload.state,
            'labels': payload.labels,
            'total': len(issues),
            'issues': issues,
        },
        x_correlation_id,
    )

@router.post('/v1/backlog/publicar-redmine/{requisito_id}')
def publicar_redmine(
    requisito_id: int,
    payload: PublicarRedmineIn | None = None,
    x_correlation_id: str | None = Header(default=None),
):
    payload = payload or PublicarRedmineIn()

    github_issues: list[dict] = []
    redmine_publish_result = {'published_count': 0, 'published_issues': [], 'warnings': []}

    if payload.use_github_import:
        if not github_redmine_import_enabled():
            raise HTTPException(status_code=409, detail='Integração GitHub→Redmine desabilitada por feature flag.')
        if not payload.github_repo:
            raise HTTPException(status_code=422, detail='Campo github_repo é obrigatório quando use_github_import=true.')

        try:
            github_issues = fetch_github_issues(
                repo=payload.github_repo,
                state=payload.github_state,
                limit=payload.github_limit,
                labels=payload.github_labels,
            )
        except IntegracaoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if payload.issue_numbers:
            selected_numbers = set(payload.issue_numbers)
            github_issues = [item for item in github_issues if item.get('number') in selected_numbers]

        redmine_publish_result = publish_issues_to_redmine(
            repo=payload.github_repo,
            issues=github_issues,
            project_id=payload.redmine_project_id,
            tracker_id=payload.tracker_id,
            priority_id=payload.priority_id,
        )

    base_id = 420
    subtarefas = [
        {'id': base_id + 1, 'subject': 'Frontend'},
        {'id': base_id + 2, 'subject': 'Backend'},
        {'id': base_id + 3, 'subject': 'Dados'},
        {'id': base_id + 4, 'subject': 'QA'},
    ]
    if github_issues:
        subtarefas = [
            {
                'id': base_id + idx + 1,
                'subject': f"GitHub #{item.get('number')} - {(item.get('title') or 'Issue sem título')[:60]}",
            }
            for idx, item in enumerate(github_issues[:4])
        ]

    return ok({
        'requisito_id': requisito_id,
        'issue_principal_id': str(base_id),
        'subtarefas': subtarefas,
        'github_repo': payload.github_repo,
        'github_imported_count': len(github_issues),
        'github_issues': github_issues,
        'redmine_published_count': redmine_publish_result['published_count'],
        'redmine_published_issues': redmine_publish_result['published_issues'],
        'warnings': redmine_publish_result['warnings'],
        'feature_enabled': github_redmine_import_enabled(),
    }, x_correlation_id)
