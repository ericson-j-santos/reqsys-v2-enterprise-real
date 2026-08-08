"""Coleta governada de informações para geração de requisitos.

O módulo fornece um contrato canônico e determinístico para receber informações
vindas do ReqSys, Microsoft Forms, Power Apps, Teams ou Power Automate. A coleta
é avaliada antes da persistência; requisitos incompletos permanecem em
refinamento e não são criados silenciosamente.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.auditoria import AuditoriaEvento
from app.repositories.requisito_repository import RequisitoRepository
from app.services.auditoria import registrar_evento
from app.services.coleta_requisitos_observabilidade import registrar_avaliacao_coleta
from app.services.coleta_requisitos_teams import (
    TIPO_EVENTO_GERADO,
    TIPO_EVENTO_REFINAMENTO,
    notificar_acompanhamento_coleta,
)

logger = logging.getLogger('reqsys.requisitos.levantamento')

router = APIRouter(prefix='/coleta', tags=['Coleta governada de requisitos'])

VERSAO_CONTRATO = '1.0.0'
PONTUACAO_MINIMA_GERACAO = 80

_ORIGENS = ('reqsys', 'microsoft_forms', 'power_apps', 'teams', 'power_automate', 'outro')
_TIPOS_DEMANDA = (
    'nova_funcionalidade',
    'alteracao',
    'correcao',
    'automacao',
    'relatorio',
    'integracao',
    'regulatorio',
)
_URGENCIAS = ('baixa', 'media', 'alta', 'critica')

_ROTULOS_TIPO = {
    'nova_funcionalidade': 'Nova funcionalidade',
    'alteracao': 'Alteração',
    'correcao': 'Correção',
    'automacao': 'Automação',
    'relatorio': 'Relatório',
    'integracao': 'Integração',
    'regulatorio': 'Regulatório',
}


class LevantamentoRequisito(BaseModel):
    """Contrato canônico de entrada, independente do canal de coleta."""

    versao_contrato: str = Field(default=VERSAO_CONTRATO, pattern=r'^\d+\.\d+\.\d+$')
    chave_idempotencia: str = Field(min_length=8, max_length=120)
    origem: Literal[
        'reqsys', 'microsoft_forms', 'power_apps', 'teams', 'power_automate', 'outro'
    ] = 'reqsys'
    solicitante: str = Field(min_length=2, max_length=120)
    area: str = Field(min_length=2, max_length=80)
    sistema: str = Field(min_length=2, max_length=80)
    tipo_demanda: Literal[
        'nova_funcionalidade',
        'alteracao',
        'correcao',
        'automacao',
        'relatorio',
        'integracao',
        'regulatorio',
    ]
    problema: str = Field(min_length=30, max_length=3000)
    objetivo: str = Field(min_length=20, max_length=2000)
    usuario_afetado: str = Field(min_length=2, max_length=300)
    processo_atual: str | None = Field(default=None, max_length=3000)
    cenario_desejado: str = Field(min_length=20, max_length=3000)
    regras_negocio: list[str] = Field(default_factory=list, max_length=20)
    criterios_aceite: list[str] = Field(min_length=1, max_length=20)
    dados_necessarios: list[str] = Field(default_factory=list, max_length=20)
    integracoes: list[str] = Field(default_factory=list, max_length=20)
    restricoes: list[str] = Field(default_factory=list, max_length=20)
    impacto_regulatorio: bool = False
    urgencia: Literal['baixa', 'media', 'alta', 'critica'] = 'media'
    data_limite: date | None = None
    referencia_externa: str | None = Field(default=None, max_length=200)
    observacoes: str | None = Field(default=None, max_length=2000)


class AvaliacaoLevantamento(BaseModel):
    pontuacao: int
    classificacao: str
    pronto_para_gerar: bool
    pendencias: list[str]
    alertas: list[str]


def _itens_validos(itens: list[str]) -> list[str]:
    return [item.strip() for item in itens if item and item.strip()]


def _avaliar_levantamento(payload: LevantamentoRequisito) -> AvaliacaoLevantamento:
    """Calcula qualidade de entrada com regra simples, explicável e testável."""

    pontuacao = 60
    pendencias: list[str] = []
    alertas: list[str] = []

    regras = _itens_validos(payload.regras_negocio)
    criterios = _itens_validos(payload.criterios_aceite)
    dados = _itens_validos(payload.dados_necessarios)
    integracoes = _itens_validos(payload.integracoes)
    restricoes = _itens_validos(payload.restricoes)

    if payload.processo_atual and payload.processo_atual.strip():
        pontuacao += 5
    else:
        pendencias.append(
            'Descrever o processo atual ou declarar explicitamente que não existe processo anterior.'
        )

    if regras:
        pontuacao += 10
    else:
        pendencias.append(
            'Confirmar as regras de negócio aplicáveis ou declarar que não há regras específicas.'
        )

    if len(criterios) >= 2:
        pontuacao += 15
    elif len(criterios) == 1:
        pontuacao += 8
        pendencias.append('Adicionar pelo menos mais um critério de aceite verificável.')
    else:
        pendencias.append('Informar ao menos um critério de aceite verificável.')

    if dados or integracoes or restricoes:
        pontuacao += 5
    else:
        alertas.append(
            'Nenhum dado, integração ou restrição foi informado; confirmar se o escopo realmente não possui dependências.'
        )

    if payload.referencia_externa and payload.referencia_externa.strip():
        pontuacao += 5
    elif payload.impacto_regulatorio:
        pendencias.append(
            'Demanda regulatória deve informar norma, política, chamado ou outra referência externa rastreável.'
        )

    if any(len(criterio) < 15 for criterio in criterios):
        alertas.append(
            'Há critério de aceite muito curto; prefira uma condição objetiva e testável.'
        )

    pontuacao = max(0, min(100, pontuacao))
    pronto = pontuacao >= PONTUACAO_MINIMA_GERACAO and not (
        payload.impacto_regulatorio and not payload.referencia_externa
    )

    if pontuacao >= 90:
        classificacao = 'ouro'
    elif pontuacao >= 80:
        classificacao = 'controlado'
    elif pontuacao >= 60:
        classificacao = 'refinamento'
    else:
        classificacao = 'incompleto'

    return AvaliacaoLevantamento(
        pontuacao=pontuacao,
        classificacao=classificacao,
        pronto_para_gerar=pronto,
        pendencias=pendencias,
        alertas=alertas,
    )


def _lista_markdown(titulo: str, itens: list[str], vazio: str) -> str:
    validos = _itens_validos(itens)
    corpo = '\n'.join(f'- {item}' for item in validos) if validos else f'- {vazio}'
    return f'## {titulo}\n{corpo}'


def _montar_requisito(payload: LevantamentoRequisito) -> dict[str, str | bool]:
    titulo_base = payload.objetivo.strip().rstrip('.')
    titulo = f"{_ROTULOS_TIPO[payload.tipo_demanda]}: {titulo_base}"
    titulo = titulo[:200]

    historia = (
        f'Como {payload.usuario_afetado.strip()}, preciso de {payload.cenario_desejado.strip()}, '
        f'para {payload.objetivo.strip()}.'
    )

    partes = [
        '## Problema',
        payload.problema.strip(),
        '## Objetivo',
        payload.objetivo.strip(),
        '## História do usuário',
        historia,
        '## Processo atual',
        payload.processo_atual.strip() if payload.processo_atual else 'Não informado.',
        _lista_markdown(
            'Regras de negócio',
            payload.regras_negocio,
            'Nenhuma regra específica informada.',
        ),
        _lista_markdown(
            'Critérios de aceite',
            payload.criterios_aceite,
            'Nenhum critério informado.',
        ),
        _lista_markdown(
            'Dados necessários',
            payload.dados_necessarios,
            'Nenhum dado adicional informado.',
        ),
        _lista_markdown(
            'Integrações',
            payload.integracoes,
            'Nenhuma integração informada.',
        ),
        _lista_markdown(
            'Restrições',
            payload.restricoes,
            'Nenhuma restrição informada.',
        ),
        '## Rastreabilidade',
        f'- Origem: {payload.origem}',
        f'- Tipo de demanda: {payload.tipo_demanda}',
        f'- Referência externa: {payload.referencia_externa or "não informada"}',
        f'- Data limite: {payload.data_limite.isoformat() if payload.data_limite else "não informada"}',
    ]
    if payload.observacoes:
        partes.extend(['## Observações', payload.observacoes.strip()])

    return {
        'titulo': titulo,
        'descricao': '\n\n'.join(partes),
        'urgencia': payload.urgencia,
        'area': payload.area.strip(),
        'sistema': payload.sistema.strip(),
        'solicitante': payload.solicitante.strip(),
        'impacto_regulatorio': payload.impacto_regulatorio,
    }


def _hash_idempotencia(chave: str) -> str:
    return hashlib.sha256(chave.encode('utf-8')).hexdigest()


def _hash_payload(payload: LevantamentoRequisito) -> str:
    canonico = json.dumps(
        payload.model_dump(mode='json'),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()


def _buscar_requisito_idempotente(db: Session, hash_idempotencia: str):
    evento = (
        db.query(AuditoriaEvento)
        .filter(
            AuditoriaEvento.acao == 'REQUISITO_GERADO_POR_COLETA',
            AuditoriaEvento.entidade == 'requisito',
            AuditoriaEvento.payload_minimo.contains(hash_idempotencia),
        )
        .order_by(AuditoriaEvento.id.desc())
        .first()
    )
    if not evento or not str(evento.entidade_id).isdigit():
        return None
    return RequisitoRepository(db).buscar_por_id(int(evento.entidade_id))


def _serializar_requisito(requisito) -> dict:
    return {
        'id': requisito.id,
        'codigo': requisito.codigo,
        'titulo': requisito.titulo,
        'descricao': requisito.descricao,
        'urgencia': requisito.urgencia,
        'area': requisito.area,
        'sistema': requisito.sistema,
        'solicitante': requisito.solicitante,
        'status': requisito.status,
        'impacto_regulatorio': requisito.impacto_regulatorio,
    }


def _contrato_formulario() -> dict:
    """Contrato declarativo para UI nativa ou mapeamento em ferramentas externas."""

    return {
        'versao_contrato': VERSAO_CONTRATO,
        'titulo': 'Levantamento estruturado para geração de requisitos',
        'objetivo': (
            'Capturar contexto suficiente para o ReqSys gerar um requisito rastreável, '
            'verificável e refinável.'
        ),
        'instrucoes': [
            'Descreva o problema e o resultado esperado; evite sugerir solução antes de explicar a necessidade.',
            'Informe critérios de aceite que outra pessoa consiga testar objetivamente.',
            'Não informe senhas, tokens, segredos, chaves de acesso ou dados pessoais desnecessários.',
            'Para anexos, prefira link corporativo governado em vez de conteúdo codificado no formulário.',
        ],
        'canais': {
            'preferencial': 'reqsys',
            'entrada_simples': 'microsoft_forms',
            'entrada_com_regras_complexas': 'power_apps',
            'integracao': 'power_automate',
        },
        'secoes': [
            {
                'id': 'identificacao',
                'titulo': 'Identificação e contexto',
                'campos': [
                    'solicitante',
                    'area',
                    'sistema',
                    'tipo_demanda',
                    'origem',
                    'referencia_externa',
                ],
            },
            {
                'id': 'necessidade',
                'titulo': 'Problema e resultado esperado',
                'campos': [
                    'problema',
                    'objetivo',
                    'usuario_afetado',
                    'processo_atual',
                    'cenario_desejado',
                ],
            },
            {
                'id': 'regras',
                'titulo': 'Regras e critérios',
                'campos': ['regras_negocio', 'criterios_aceite', 'impacto_regulatorio'],
            },
            {
                'id': 'dependencias',
                'titulo': 'Dados, integrações e restrições',
                'campos': [
                    'dados_necessarios',
                    'integracoes',
                    'restricoes',
                    'urgencia',
                    'data_limite',
                    'observacoes',
                ],
            },
        ],
        'opcoes': {
            'origem': list(_ORIGENS),
            'tipo_demanda': list(_TIPOS_DEMANDA),
            'urgencia': list(_URGENCIAS),
        },
        'regra_geracao': {
            'pontuacao_minima': PONTUACAO_MINIMA_GERACAO,
            'impacto_regulatorio_exige_referencia': True,
            'persistencia_idempotente': True,
        },
    }


@router.get('/formulario')
def obter_formulario(x_correlation_id: str | None = Header(default=None)):
    return ok(
        _contrato_formulario(),
        x_correlation_id,
        meta={'contract': 'reqsys-coleta-requisito-v1'},
    )


@router.post('/previsualizar')
async def previsualizar_requisito(
    payload: LevantamentoRequisito,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    avaliacao = _avaliar_levantamento(payload)
    requisito = _montar_requisito(payload)
    hash_idempotencia = _hash_idempotencia(payload.chave_idempotencia)
    payload_hash = _hash_payload(payload)
    correlation_id = x_correlation_id or f'coleta-{hash_idempotencia[:24]}'

    registrar_avaliacao_coleta(
        db,
        payload=payload,
        avaliacao=avaliacao,
        hash_idempotencia=hash_idempotencia,
        payload_hash=payload_hash,
        correlation_id=correlation_id,
    )

    acompanhamento_teams = None
    if not avaliacao.pronto_para_gerar:
        acompanhamento_teams = await notificar_acompanhamento_coleta(
            db,
            tipo_evento=TIPO_EVENTO_REFINAMENTO,
            payload=payload,
            avaliacao=avaliacao,
            hash_idempotencia=hash_idempotencia,
            payload_hash=payload_hash,
            correlation_id=correlation_id,
        )

    return ok(
        {
            'versao_contrato': VERSAO_CONTRATO,
            'avaliacao': avaliacao.model_dump(),
            'requisito_proposto': requisito,
            'persistido': False,
            'acompanhamento_teams': acompanhamento_teams,
        },
        correlation_id,
        meta={'contract': 'reqsys-coleta-requisito-v1'},
    )


@router.post('/gerar', status_code=status.HTTP_200_OK)
async def gerar_requisito(
    payload: LevantamentoRequisito,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    avaliacao = _avaliar_levantamento(payload)
    hash_idempotencia = _hash_idempotencia(payload.chave_idempotencia)
    payload_hash = _hash_payload(payload)
    correlation_id = x_correlation_id or f'coleta-{hash_idempotencia[:24]}'

    registrar_avaliacao_coleta(
        db,
        payload=payload,
        avaliacao=avaliacao,
        hash_idempotencia=hash_idempotencia,
        payload_hash=payload_hash,
        correlation_id=correlation_id,
        somente_se_payload_novo=True,
    )

    if not avaliacao.pronto_para_gerar:
        acompanhamento_teams = await notificar_acompanhamento_coleta(
            db,
            tipo_evento=TIPO_EVENTO_REFINAMENTO,
            payload=payload,
            avaliacao=avaliacao,
            hash_idempotencia=hash_idempotencia,
            payload_hash=payload_hash,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                'code': 'LEVANTAMENTO_REQUER_REFINAMENTO',
                'message': (
                    'A coleta ainda não atingiu o nível mínimo para gerar um requisito governado.'
                ),
                'pontuacao': avaliacao.pontuacao,
                'pontuacao_minima': PONTUACAO_MINIMA_GERACAO,
                'pendencias': avaliacao.pendencias,
                'alertas': avaliacao.alertas,
                'acompanhamento_teams': acompanhamento_teams,
            },
        )

    existente = _buscar_requisito_idempotente(db, hash_idempotencia)
    if existente:
        acompanhamento_teams = await notificar_acompanhamento_coleta(
            db,
            tipo_evento=TIPO_EVENTO_GERADO,
            payload=payload,
            avaliacao=avaliacao,
            hash_idempotencia=hash_idempotencia,
            payload_hash=payload_hash,
            correlation_id=correlation_id,
            requisito=existente,
        )
        logger.info(
            'coleta_requisito_reutilizada codigo=%s origem=%s correlation_id=%s',
            existente.codigo,
            payload.origem,
            correlation_id,
        )
        return ok(
            {
                'versao_contrato': VERSAO_CONTRATO,
                'avaliacao': avaliacao.model_dump(),
                'requisito': _serializar_requisito(existente),
                'persistido': True,
                'reutilizado': True,
                'acompanhamento_teams': acompanhamento_teams,
            },
            correlation_id,
            meta={'contract': 'reqsys-coleta-requisito-v1'},
        )

    dados_requisito = _montar_requisito(payload)
    codigo = f'REQ-{uuid4().hex[:12].upper()}'
    requisito = RequisitoRepository(db).criar(
        codigo=codigo,
        status='recebido',
        **dados_requisito,
    )

    evidencia = {
        'schema_version': '1.0.0',
        'versao_contrato': VERSAO_CONTRATO,
        'origem': payload.origem,
        'tipo_demanda': payload.tipo_demanda,
        'pontuacao': avaliacao.pontuacao,
        'classificacao': avaliacao.classificacao,
        'chave_idempotencia_hash': hash_idempotencia,
        'payload_hash': payload_hash,
    }
    registrar_evento(
        db,
        correlation_id,
        payload.solicitante,
        'REQUISITO_GERADO_POR_COLETA',
        'requisito',
        requisito.id,
        json.dumps(evidencia, ensure_ascii=False, separators=(',', ':')),
    )

    acompanhamento_teams = await notificar_acompanhamento_coleta(
        db,
        tipo_evento=TIPO_EVENTO_GERADO,
        payload=payload,
        avaliacao=avaliacao,
        hash_idempotencia=hash_idempotencia,
        payload_hash=payload_hash,
        correlation_id=correlation_id,
        requisito=requisito,
    )

    logger.info(
        'coleta_requisito_gerada codigo=%s score=%s origem=%s correlation_id=%s',
        requisito.codigo,
        avaliacao.pontuacao,
        payload.origem,
        correlation_id,
    )
    return ok(
        {
            'versao_contrato': VERSAO_CONTRATO,
            'avaliacao': avaliacao.model_dump(),
            'requisito': _serializar_requisito(requisito),
            'persistido': True,
            'reutilizado': False,
            'acompanhamento_teams': acompanhamento_teams,
        },
        correlation_id,
        meta={'contract': 'reqsys-coleta-requisito-v1'},
    )
