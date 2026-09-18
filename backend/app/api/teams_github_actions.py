from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.services.auditoria import registrar_evento
from app.services.teams_github_actions import (
    TeamsGithubActionsError,
    despachar_verificacoes_github,
    status_teams_github_actions,
)

router = APIRouter(prefix='/github-actions', tags=['Teams GitHub Actions'])
require_github_actions_auth = require_admin_or_service_token('teams_gateway:github_actions')


class TeamsGithubActionsDispatchRequest(BaseModel):
    mode: Literal['essential', 'all'] = 'essential'
    ref: str = Field(default='main', min_length=1, max_length=200)

    @field_validator('ref')
    @classmethod
    def normalizar_ref(cls, value: str) -> str:
        return value.strip()


class TeamsGithubActionsCardRequest(BaseModel):
    titulo: str = Field(default='ReqSys — ação disponível', min_length=1, max_length=200)
    descricao: str = Field(default='Execute as verificações sem sair do Teams.', min_length=1, max_length=2000)
    ref: str = Field(default='main', min_length=1, max_length=200)
    github_url: str | None = Field(default=None, max_length=1000)

    @field_validator('titulo', 'descricao', 'ref', 'github_url', mode='before')
    @classmethod
    def normalizar_texto(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


def _acao_cartao(
    *,
    titulo: str,
    mode: Literal['essential', 'all'],
    ref: str,
    correlation_id: str,
) -> dict:
    return {
        'type': 'Action.Submit',
        'title': titulo,
        'data': {
            'reqsys_action': 'github_actions_dispatch',
            'mode': mode,
            'ref': ref,
            'correlation_id': correlation_id,
        },
    }


def construir_cartao(payload: TeamsGithubActionsCardRequest, correlation_id: str) -> dict:
    actions = [
        _acao_cartao(
            titulo='Executar verificações essenciais',
            mode='essential',
            ref=payload.ref,
            correlation_id=correlation_id,
        ),
        _acao_cartao(
            titulo='Executar verificações completas',
            mode='all',
            ref=payload.ref,
            correlation_id=correlation_id,
        ),
    ]
    if payload.github_url:
        actions.append({'type': 'Action.OpenUrl', 'title': 'Abrir no GitHub', 'url': payload.github_url})

    return {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': '1.4',
        'msteams': {'width': 'Full'},
        'body': [
            {
                'type': 'TextBlock',
                'text': payload.titulo,
                'weight': 'Bolder',
                'size': 'Medium',
                'wrap': True,
            },
            {'type': 'TextBlock', 'text': payload.descricao, 'wrap': True},
            {
                'type': 'FactSet',
                'facts': [
                    {'title': 'Ref', 'value': payload.ref},
                    {'title': 'Controle', 'value': 'ações previamente permitidas pelo ReqSys'},
                ],
            },
            {
                'type': 'ActionSet',
                'actions': actions,
            },
        ],
    }


@router.get('/status')
def teams_github_actions_status(
    _ctx: ServiceAuthContext = Depends(require_github_actions_auth),
):
    """Expõe apenas estado seguro da integração, nunca o token GitHub."""
    return ok(status_teams_github_actions())


@router.post('/card')
def teams_github_actions_card(
    payload: TeamsGithubActionsCardRequest,
    _ctx: ServiceAuthContext = Depends(require_github_actions_auth),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Gera o Adaptive Card compatível com o Flow bot atual."""
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    return ok({'adaptive_card': construir_cartao(payload, correlation_id)}, correlation_id)


@router.post('/dispatch')
async def teams_github_actions_dispatch(
    payload: TeamsGithubActionsDispatchRequest,
    ctx: ServiceAuthContext = Depends(require_github_actions_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Executa somente o dispatcher central, com modo/ref validados no servidor."""
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    registrar_evento(
        db,
        correlation_id,
        ctx.ator,
        'TEAMS_GITHUB_ACTION_SOLICITADA',
        'github_actions',
        f'{payload.mode}:{payload.ref}',
    )
    try:
        result = await despachar_verificacoes_github(
            mode=payload.mode,
            target_ref=payload.ref,
            correlation_id=correlation_id,
            actor=ctx.ator,
        )
    except TeamsGithubActionsError as exc:
        registrar_evento(
            db,
            correlation_id,
            ctx.ator,
            'TEAMS_GITHUB_ACTION_FALHOU',
            'github_actions',
            f'{payload.mode}:{payload.ref}',
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None

    registrar_evento(
        db,
        correlation_id,
        ctx.ator,
        'TEAMS_GITHUB_ACTION_DISPARADA',
        'github_actions',
        f'{payload.mode}:{payload.ref}',
    )
    return ok(result, correlation_id)
