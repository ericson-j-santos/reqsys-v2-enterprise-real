from time import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito
from app.services.github_redmine import (
    IntegracaoError,
    fetch_github_issues,
    github_redmine_import_enabled,
    publish_issues_to_redmine,
    publish_requisito_to_redmine,
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

@router.post('/v1/solicitacoes', status_code=201)
def criar_solicitacao(
    payload: SolicitacaoIn,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    codigo = f"SOL-{uuid4().hex[:9].upper()}"
    req = Requisito(
        codigo=codigo,
        titulo=payload.titulo,
        descricao=payload.descricao,
        urgencia=payload.urgencia or 'media',
        area=payload.area,
        sistema=payload.sistema,
        solicitante=payload.solicitante,
        status='recebido',
        impacto_regulatorio=payload.impacto_regulatorio,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return ok({'id': req.id, 'codigo': req.codigo, 'status': req.status}, x_correlation_id)

@router.post('/v1/requisitos/validar')
def validar_requisito(
    payload: ValidacaoIn,
    requisito_id: int | None = None,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    texto = f"{payload.titulo or ''} {payload.descricao or ''}".lower()
    ambiguos = [t for t in ['rápido', 'melhor', 'simples', 'fácil', 'intuitivo', 'otimizado'] if t in texto]
    alertas: list[str] = []
    if not payload.requisitos_funcionais:
        alertas.append('Nenhum requisito funcional identificado.')
    if not payload.criterios_aceite:
        alertas.append('Nenhum critério de aceite informado.')
    for termo in ambiguos:
        alertas.append(f"Termo ambíguo detectado: '{termo}'")
    aprovado = len(alertas) == 0

    if requisito_id:
        req = db.get(Requisito, requisito_id)
        if req and req.status == 'recebido':
            req.status = 'validado'
            db.commit()

    return ok({'aprovado_para_triagem': aprovado, 'alertas': alertas, 'requisito_id': requisito_id}, x_correlation_id)


@router.post('/v1/requisitos/estruturar/{requisito_id}')
def estruturar_requisito(
    requisito_id: int,
    payload: SolicitacaoIn,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    req = db.get(Requisito, requisito_id)
    if req and req.status in ('recebido', 'validado'):
        req.status = 'estruturado'
        db.commit()

    codigo = req.codigo if req else f"REQ-{str(int(time()))[-8:]}"
    return ok({
        'requisito_id': requisito_id,
        'codigo_requisito': codigo,
        'status': req.status if req else 'estruturado',
        'tipo': 'funcional',
        'prioridade': payload.urgencia or 'media',
        'requisitos_funcionais': inferir_rfs(payload.descricao),
        'requisitos_nao_funcionais': [
            'Registrar correlation_id.',
            'Acesso respeita perfil do usuario.',
            'Resposta <= 2s (p95).',
        ],
        'regras_negocio': [{'codigo': 'RN-001', 'descricao': 'Nao permitir cadastro ativo duplicado.'}],
        'criterios_aceite': [
            {'ordem': 1, 'descricao': 'Identificador existente: dados exibidos.'},
            {'ordem': 2, 'descricao': 'Identificador inexistente: permitir novo cadastro.'},
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
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    payload = payload or PublicarRedmineIn()

    requisito = db.get(Requisito, requisito_id)
    if not requisito:
        raise HTTPException(status_code=404, detail=f'Requisito {requisito_id} nao encontrado.')

    github_issues: list[dict] = []
    github_publish_result = {'published_count': 0, 'published_issues': [], 'warnings': []}

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
            github_issues = [i for i in github_issues if i.get('number') in selected_numbers]

        github_publish_result = publish_issues_to_redmine(
            repo=payload.github_repo,
            issues=github_issues,
            project_id=payload.redmine_project_id,
            tracker_id=payload.tracker_id,
            priority_id=payload.priority_id,
        )

    result = publish_requisito_to_redmine(
        requisito=requisito,
        project_id=payload.redmine_project_id,
        tracker_id=payload.tracker_id,
        priority_id=payload.priority_id,
    )

    if result['issue_principal_id'] and requisito.status not in ('backlog', 'concluido', 'cancelado'):
        requisito.status = 'backlog'
        db.commit()

    warnings = result['warnings'] + github_publish_result['warnings']

    return ok({
        'requisito_id': requisito_id,
        'codigo': requisito.codigo,
        'issue_principal_id': result['issue_principal_id'],
        'subtarefas': result['subtarefas'],
        'github_repo': payload.github_repo,
        'github_imported_count': len(github_issues),
        'github_issues': github_issues,
        'redmine_published_count': github_publish_result['published_count'],
        'redmine_published_issues': github_publish_result['published_issues'],
        'warnings': warnings,
        'feature_enabled': github_redmine_import_enabled(),
    }, x_correlation_id)
