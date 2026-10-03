import json
from time import time_ns

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.agile_runtime import (
    AgileCeremony,
    AgileCeremonyAction,
    AgileEvidence,
    AgileSprint,
    AgileWorkItem,
)
from app.schemas.agile_runtime import (
    AgileAIRoutingRecommendationOut,
    AgileCeremonyActionCriar,
    AgileCeremonyActionOut,
    AgileCeremonyActionStatus,
    AgileCeremonyConcluir,
    AgileCeremonyCriar,
    AgileCeremonyOut,
    AgileEvidenceCriar,
    AgileEvidenceOut,
    AgileGithubLaunchpadOut,
    AgileRuntimeResumo,
    AgileSprintCriar,
    AgileSprintOut,
    AgileSprintStatusAtualizar,
    AgileTraceabilityAtualizar,
    AgileWorkflowTransicao,
    AgileWorkItemCriar,
    AgileWorkItemOut,
    GithubBranchCriarIn,
    GithubBranchCriarOut,
)
from app.services.agile_ai_router import recomendar_roteamento_multi_ia
from app.services.auditoria import registrar_evento
from app.services.github_branch_service import GithubBranchError, criar_branch_work_item
from app.services.github_launchpad import (
    montar_github_launchpad,
    normalizar_ambiente_launchpad,
)

router = APIRouter(prefix='/v1/agile-runtime', tags=['Agile Runtime'])

STATUS_TRANSITIONS: dict[str, set[str]] = {
    'novo': {'refinando', 'cancelado'},
    'refinando': {'pronto_para_sprint', 'bloqueado', 'cancelado'},
    'pronto_para_sprint': {'planejado', 'refinando', 'bloqueado'},
    'planejado': {'em_execucao', 'bloqueado', 'cancelado'},
    'em_execucao': {'em_revisao', 'bloqueado', 'reprovado'},
    'em_revisao': {'em_ci', 'em_execucao', 'reprovado'},
    'em_ci': {'homologacao', 'reprovado', 'em_execucao'},
    'homologacao': {'evidenciado', 'reprovado'},
    'evidenciado': {'producao', 'reaberto'},
    'producao': {'monitorado', 'reaberto'},
    'monitorado': {'concluido', 'reaberto'},
    'concluido': {'reaberto'},
    'bloqueado': {'refinando', 'planejado', 'em_execucao', 'cancelado'},
    'reprovado': {'em_execucao', 'em_revisao', 'em_ci', 'cancelado'},
    'cancelado': {'reaberto'},
    'reaberto': {'refinando', 'em_execucao', 'cancelado'},
}


def _codigo(prefixo: str) -> str:
    return f'{prefixo}-{str(time_ns())[-9:]}'


def _get_work_item(db: Session, work_item_id: int) -> AgileWorkItem:
    item = db.get(AgileWorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail='Item de trabalho ágil não encontrado')
    return item


def _get_sprint(db: Session, sprint_id: int) -> AgileSprint:
    sprint = db.get(AgileSprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail='Sprint não encontrada')
    return sprint


def _get_ceremony(db: Session, ceremony_id: int) -> AgileCeremony:
    ceremony = db.get(AgileCeremony, ceremony_id)
    if not ceremony:
        raise HTTPException(status_code=404, detail='Cerimônia ágil não encontrada')
    return ceremony


def _ceremony_out(ceremony: AgileCeremony) -> dict:
    return AgileCeremonyOut(
        id=ceremony.id,
        codigo=ceremony.codigo,
        sprint_id=ceremony.sprint_id,
        tipo=ceremony.tipo,
        titulo=ceremony.titulo,
        inicio_em=ceremony.inicio_em,
        duracao_minutos=ceremony.duracao_minutos,
        facilitador=ceremony.facilitador,
        participantes=json.loads(ceremony.participantes_json),
        pauta=ceremony.pauta,
        resumo=ceremony.resumo,
        decisoes=ceremony.decisoes,
        status=ceremony.status,
        correlation_id=ceremony.correlation_id,
        criado_em=ceremony.criado_em,
    ).model_dump()


def _validar_gate(item: AgileWorkItem, destino: str) -> None:
    faltantes = []
    if destino == 'pronto_para_sprint':
        if not item.criterios_aceite:
            faltantes.append('criterios_aceite')
        if not item.sprint_id:
            faltantes.append('sprint_id')
        if not item.owner_ai:
            faltantes.append('owner')
        if item.pontos <= 0:
            faltantes.append('pontos')
    elif destino == 'concluido':
        if not item.change_url:
            faltantes.append('change_url')
        if item.ci_status == 'unknown':
            faltantes.append('ci_status')
        if item.ambiente_deploy == 'none':
            faltantes.append('ambiente_deploy')
        if not item.evidencias:
            faltantes.append('evidencias')
    if faltantes:
        raise HTTPException(status_code=422, detail={'gate': destino, 'campos_faltantes': faltantes})


def _routing_out(item: AgileWorkItem, modo: str = 'preview') -> AgileAIRoutingRecommendationOut:
    recomendacao = recomendar_roteamento_multi_ia(item)
    return AgileAIRoutingRecommendationOut(
        work_item_id=item.id,
        work_item_codigo=item.codigo,
        owner_ai=recomendacao.owner_ai,
        categoria=recomendacao.categoria,
        labels=recomendacao.labels,
        branch_sugerida=recomendacao.branch_sugerida,
        pipeline_sugerido=recomendacao.pipeline_sugerido,
        prioridade_sugerida=recomendacao.prioridade_sugerida,
        confianca=recomendacao.confianca,
        justificativas=recomendacao.justificativas,
        acoes_recomendadas=recomendacao.acoes_recomendadas,
        modo=modo,
    )


@router.get('/resumo')
def resumo(db: Session = Depends(get_db)):
    total_itens = db.query(AgileWorkItem).count()
    total_sprints = db.query(AgileSprint).count()
    total_evidencias = db.query(AgileEvidence).count()
    itens_concluidos = db.query(AgileWorkItem).filter(AgileWorkItem.status == 'concluido').count()
    itens_em_ci = db.query(AgileWorkItem).filter(AgileWorkItem.status == 'em_ci').count()
    itens_bloqueados = db.query(AgileWorkItem).filter(AgileWorkItem.status == 'bloqueado').count()
    ci_total = db.query(AgileWorkItem).filter(AgileWorkItem.ci_status != 'unknown').count()
    ci_success = db.query(AgileWorkItem).filter(AgileWorkItem.ci_status == 'success').count()

    payload = AgileRuntimeResumo(
        total_itens=total_itens,
        total_sprints=total_sprints,
        total_evidencias=total_evidencias,
        itens_concluidos=itens_concluidos,
        itens_em_ci=itens_em_ci,
        itens_bloqueados=itens_bloqueados,
        conclusao_percentual=round((itens_concluidos / total_itens * 100), 2) if total_itens else 0.0,
        ci_success_percentual=round((ci_success / ci_total * 100), 2) if ci_total else 0.0,
    )
    return ok(payload.model_dump())


@router.get('/sprints')
def listar_sprints(db: Session = Depends(get_db)):
    sprints = db.query(AgileSprint).order_by(AgileSprint.id.desc()).all()
    return ok([AgileSprintOut.model_validate(sprint).model_dump() for sprint in sprints])


@router.post('/sprints')
def criar_sprint(payload: AgileSprintCriar, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    if payload.data_fim < payload.data_inicio:
        raise HTTPException(status_code=422, detail='data_fim deve ser maior ou igual a data_inicio')

    sprint = AgileSprint(codigo=_codigo('SPR'), **payload.model_dump())
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        'agile-runtime',
        'AGILE_SPRINT_CRIADA',
        'agile_sprint',
        sprint.id,
        '{"campos":"minimizados"}',
    )
    return ok(AgileSprintOut.model_validate(sprint).model_dump(), x_correlation_id)


@router.patch('/sprints/{sprint_id}/status')
def atualizar_status_sprint(
    sprint_id: int,
    payload: AgileSprintStatusAtualizar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    sprint = _get_sprint(db, sprint_id)
    transicoes = {
        'planejada': {'ativa', 'cancelada'},
        'ativa': {'concluida', 'cancelada'},
        'concluida': set(),
        'cancelada': set(),
    }
    if payload.status not in transicoes.get(sprint.status, set()):
        raise HTTPException(status_code=409, detail=f'Transição inválida de sprint: {sprint.status} -> {payload.status}')
    sprint.status = payload.status
    if payload.status == 'concluida':
        sprint.pontos_concluidos = sum(item.pontos for item in sprint.itens if item.status == 'concluido')
    db.commit()
    db.refresh(sprint)
    registrar_evento(db, x_correlation_id or 'sem-correlation-id', 'agile-runtime', 'AGILE_SPRINT_STATUS_ATUALIZADO', 'agile_sprint', sprint.id, '{"campos":"minimizados"}')
    return ok(AgileSprintOut.model_validate(sprint).model_dump(), x_correlation_id)


@router.get('/cerimonias')
def listar_cerimonias(sprint_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(AgileCeremony)
    if sprint_id is not None:
        query = query.filter(AgileCeremony.sprint_id == sprint_id)
    return ok([_ceremony_out(item) for item in query.order_by(AgileCeremony.inicio_em.desc()).all()])


@router.post('/cerimonias')
def criar_cerimonia(
    payload: AgileCeremonyCriar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    _get_sprint(db, payload.sprint_id)
    data = payload.model_dump(exclude={'participantes'})
    ceremony = AgileCeremony(
        codigo=_codigo('CER'),
        participantes_json=json.dumps(payload.participantes, ensure_ascii=False),
        correlation_id=x_correlation_id or 'sem-correlation-id',
        **data,
    )
    db.add(ceremony)
    db.commit()
    db.refresh(ceremony)
    registrar_evento(db, ceremony.correlation_id, 'agile-runtime', 'AGILE_CERIMONIA_CRIADA', 'agile_ceremony', ceremony.id, '{"campos":"minimizados"}')
    return ok(_ceremony_out(ceremony), x_correlation_id)


@router.post('/cerimonias/{ceremony_id}/concluir')
def concluir_cerimonia(
    ceremony_id: int,
    payload: AgileCeremonyConcluir,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    ceremony = _get_ceremony(db, ceremony_id)
    if ceremony.status != 'agendada':
        raise HTTPException(status_code=409, detail='Somente cerimônia agendada pode ser concluída')
    ceremony.resumo = payload.resumo
    ceremony.decisoes = payload.decisoes
    ceremony.status = 'concluida'
    db.commit()
    db.refresh(ceremony)
    registrar_evento(db, x_correlation_id or ceremony.correlation_id, 'agile-runtime', 'AGILE_CERIMONIA_CONCLUIDA', 'agile_ceremony', ceremony.id, '{"campos":"minimizados"}')
    return ok(_ceremony_out(ceremony), x_correlation_id)


@router.get('/cerimonias/{ceremony_id}/acoes')
def listar_acoes_cerimonia(ceremony_id: int, db: Session = Depends(get_db)):
    _get_ceremony(db, ceremony_id)
    items = db.query(AgileCeremonyAction).filter(AgileCeremonyAction.cerimonia_id == ceremony_id).order_by(AgileCeremonyAction.id.desc()).all()
    return ok([AgileCeremonyActionOut.model_validate(item).model_dump() for item in items])


@router.post('/cerimonias/{ceremony_id}/acoes')
def criar_acao_cerimonia(
    ceremony_id: int,
    payload: AgileCeremonyActionCriar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    _get_ceremony(db, ceremony_id)
    item = AgileCeremonyAction(cerimonia_id=ceremony_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    registrar_evento(db, x_correlation_id or 'sem-correlation-id', 'agile-runtime', 'AGILE_ACAO_CERIMONIA_CRIADA', 'agile_ceremony_action', item.id, '{"campos":"minimizados"}')
    return ok(AgileCeremonyActionOut.model_validate(item).model_dump(), x_correlation_id)


@router.patch('/cerimonias/{ceremony_id}/acoes/{action_id}')
def atualizar_acao_cerimonia(
    ceremony_id: int,
    action_id: int,
    payload: AgileCeremonyActionStatus,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    _get_ceremony(db, ceremony_id)
    item = db.get(AgileCeremonyAction, action_id)
    if not item or item.cerimonia_id != ceremony_id:
        raise HTTPException(status_code=404, detail='Ação da cerimônia não encontrada')
    item.status = payload.status
    db.commit()
    db.refresh(item)
    registrar_evento(db, x_correlation_id or 'sem-correlation-id', 'agile-runtime', 'AGILE_ACAO_CERIMONIA_ATUALIZADA', 'agile_ceremony_action', item.id, '{"campos":"minimizados"}')
    return ok(AgileCeremonyActionOut.model_validate(item).model_dump(), x_correlation_id)


@router.get('/work-items')
def listar_work_items(db: Session = Depends(get_db)):
    itens = db.query(AgileWorkItem).order_by(AgileWorkItem.id.desc()).all()
    return ok([AgileWorkItemOut.model_validate(item).model_dump() for item in itens])


@router.post('/work-items')
def criar_work_item(payload: AgileWorkItemCriar, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    item = AgileWorkItem(codigo=_codigo('AGI'), **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        'agile-runtime',
        'AGILE_WORK_ITEM_CRIADO',
        'agile_work_item',
        item.id,
        '{"campos":"minimizados"}',
    )
    return ok(AgileWorkItemOut.model_validate(item).model_dump(), x_correlation_id)


@router.get('/work-items/{work_item_id}/github-launchpad')
def github_launchpad_work_item(
    work_item_id: int,
    ambiente: str = Query(default='dev', description='Ambiente alvo: dev, test, homolog ou prod'),
    db: Session = Depends(get_db),
):
    item = _get_work_item(db, work_item_id)
    try:
        normalizar_ambiente_launchpad(ambiente)
        payload = montar_github_launchpad(item, ambiente, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(AgileGithubLaunchpadOut.model_validate(payload).model_dump())


@router.post('/work-items/{work_item_id}/github/branch')
def criar_branch_github_work_item(
    work_item_id: int,
    payload: GithubBranchCriarIn,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    item = _get_work_item(db, work_item_id)
    try:
        normalizar_ambiente_launchpad(payload.ambiente)
        resultado = criar_branch_work_item(
            db,
            item,
            payload.ambiente,
            correlation_id=x_correlation_id or 'sem-correlation-id',
            criar_se_ausente=payload.criar_se_ausente,
            aplicar_branch_no_item=payload.aplicar_branch_no_item,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GithubBranchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(GithubBranchCriarOut.model_validate(resultado).model_dump(), x_correlation_id)


@router.get('/work-items/{work_item_id}/ai-routing/preview')
def preview_roteamento_multi_ia(work_item_id: int, db: Session = Depends(get_db)):
    item = _get_work_item(db, work_item_id)
    return ok(_routing_out(item, 'preview').model_dump())


@router.post('/work-items/{work_item_id}/ai-routing/apply')
def aplicar_roteamento_multi_ia(
    work_item_id: int,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    item = _get_work_item(db, work_item_id)
    routing = _routing_out(item, 'aplicado')
    item.owner_ai = routing.owner_ai
    item.prioridade = routing.prioridade_sugerida
    if not item.branch:
        item.branch = routing.branch_sugerida
    db.add(item)
    db.commit()
    db.refresh(item)

    evidencia = AgileEvidence(
        work_item_id=item.id,
        tipo='auditoria',
        titulo='Roteamento Multi-IA aplicado',
        status='aplicado',
        observacao=(
            f'owner_ai={routing.owner_ai}; categoria={routing.categoria}; '
            f'pipeline={routing.pipeline_sugerido}; confianca={routing.confianca}'
        ),
        correlation_id=x_correlation_id or 'sem-correlation-id',
        criado_por='multi-ia-sprint-router',
    )
    db.add(evidencia)
    db.commit()

    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        'multi-ia-sprint-router',
        'AGILE_MULTI_IA_ROUTING_APLICADO',
        'agile_work_item',
        item.id,
        '{"campos":"minimizados"}',
    )
    return ok(routing.model_dump(), x_correlation_id)


@router.patch('/work-items/{work_item_id}/workflow')
def transicionar_work_item(
    work_item_id: int,
    payload: AgileWorkflowTransicao,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    item = _get_work_item(db, work_item_id)
    status_atual = item.status
    proximos = STATUS_TRANSITIONS.get(status_atual, set())
    if payload.status not in proximos:
        raise HTTPException(
            status_code=409,
            detail=f'Transicao invalida: {status_atual} -> {payload.status}',
        )

    _validar_gate(item, payload.status)

    item.status = payload.status
    db.add(item)
    db.commit()
    db.refresh(item)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        'agile-runtime',
        'AGILE_WORKFLOW_TRANSICIONADO',
        'agile_work_item',
        item.id,
        '{"campos":"minimizados"}',
    )
    return ok(AgileWorkItemOut.model_validate(item).model_dump(), x_correlation_id)


@router.patch('/work-items/{work_item_id}/traceability')
def atualizar_rastreabilidade(
    work_item_id: int,
    payload: AgileTraceabilityAtualizar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    item = _get_work_item(db, work_item_id)
    for campo, valor in payload.model_dump().items():
        setattr(item, campo, valor)
    db.add(item)
    db.commit()
    db.refresh(item)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        'agile-runtime',
        'AGILE_TRACEABILITY_ATUALIZADA',
        'agile_work_item',
        item.id,
        '{"campos":"minimizados"}',
    )
    return ok(AgileWorkItemOut.model_validate(item).model_dump(), x_correlation_id)


@router.get('/work-items/{work_item_id}/evidences')
def listar_evidencias(work_item_id: int, db: Session = Depends(get_db)):
    _get_work_item(db, work_item_id)
    evidencias = db.query(AgileEvidence).filter(AgileEvidence.work_item_id == work_item_id).order_by(AgileEvidence.id.desc()).all()
    return ok([AgileEvidenceOut.model_validate(evidencia).model_dump() for evidencia in evidencias])


@router.post('/work-items/{work_item_id}/evidences')
def criar_evidencia(
    work_item_id: int,
    payload: AgileEvidenceCriar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    _get_work_item(db, work_item_id)
    evidencia = AgileEvidence(
        work_item_id=work_item_id,
        correlation_id=x_correlation_id or 'sem-correlation-id',
        **payload.model_dump(),
    )
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        payload.criado_por or 'agile-runtime',
        'AGILE_EVIDENCIA_REGISTRADA',
        'agile_evidence',
        evidencia.id,
        '{"campos":"minimizados"}',
    )
    return ok(AgileEvidenceOut.model_validate(evidencia).model_dump(), x_correlation_id)
