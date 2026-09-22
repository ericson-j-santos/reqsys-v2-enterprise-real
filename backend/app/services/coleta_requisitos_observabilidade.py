"""Observabilidade da coleta governada de requisitos.

A telemetria deste módulo é deliberadamente mínima: registra apenas metadados de
qualidade, hashes e códigos estáveis de pendência. O conteúdo funcional informado
pelo solicitante não é duplicado na auditoria.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaEvento
from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.services.auditoria import registrar_evento

ACAO_COLETA_AVALIADA = 'COLETA_REQUISITO_AVALIADA'
ACAO_REQUISITO_GERADO = 'REQUISITO_GERADO_POR_COLETA'
VERSAO_CONTRATO_OBSERVABILIDADE = '1.1.0'

ROTULOS_PENDENCIA = {
    'PROCESSO_ATUAL_NAO_INFORMADO': 'Processo atual não informado',
    'REGRAS_NEGOCIO_NAO_INFORMADAS': 'Regras de negócio não informadas',
    'CRITERIOS_ACEITE_INSUFICIENTES': 'Critérios de aceite insuficientes',
    'REFERENCIA_REGULATORIA_NAO_INFORMADA': 'Referência regulatória não informada',
}


def _itens_validos(itens) -> list[str]:
    return [str(item).strip() for item in (itens or []) if str(item).strip()]


def codigos_pendencia(payload) -> list[str]:
    """Retorna códigos estáveis sem repetir o texto funcional da coleta."""

    codigos: list[str] = []
    if not str(payload.processo_atual or '').strip():
        codigos.append('PROCESSO_ATUAL_NAO_INFORMADO')
    if not _itens_validos(payload.regras_negocio):
        codigos.append('REGRAS_NEGOCIO_NAO_INFORMADAS')
    if len(_itens_validos(payload.criterios_aceite)) < 2:
        codigos.append('CRITERIOS_ACEITE_INSUFICIENTES')
    if payload.impacto_regulatorio and not str(payload.referencia_externa or '').strip():
        codigos.append('REFERENCIA_REGULATORIA_NAO_INFORMADA')
    return codigos


def _evento_avaliacao_existente(
    db: Session,
    hash_idempotencia: str,
    payload_hash: str,
) -> bool:
    return (
        db.query(AuditoriaEvento.id)
        .filter(
            AuditoriaEvento.acao == ACAO_COLETA_AVALIADA,
            AuditoriaEvento.payload_minimo.contains(hash_idempotencia),
            AuditoriaEvento.payload_minimo.contains(payload_hash),
        )
        .first()
        is not None
    )


def registrar_avaliacao_coleta(
    db: Session,
    *,
    payload,
    avaliacao,
    hash_idempotencia: str,
    payload_hash: str,
    correlation_id: str,
    somente_se_payload_novo: bool = False,
) -> bool:
    """Registra uma avaliação sem persistir o conteúdo da necessidade.

    Em chamadas de geração, ``somente_se_payload_novo`` evita contar novamente a
    mesma avaliação que já foi registrada pela pré-visualização.
    """

    if somente_se_payload_novo and _evento_avaliacao_existente(
        db,
        hash_idempotencia,
        payload_hash,
    ):
        return False

    evidencia = {
        'schema_version': VERSAO_CONTRATO_OBSERVABILIDADE,
        'versao_contrato': payload.versao_contrato,
        'origem': payload.origem,
        'tipo_demanda': payload.tipo_demanda,
        'pontuacao': avaliacao.pontuacao,
        'classificacao': avaliacao.classificacao,
        'pronto_para_gerar': avaliacao.pronto_para_gerar,
        'codigos_pendencia': codigos_pendencia(payload),
        'quantidade_alertas': len(avaliacao.alertas),
        'chave_idempotencia_hash': hash_idempotencia,
        'payload_hash': payload_hash,
    }
    registrar_evento(
        db,
        correlation_id,
        payload.solicitante,
        ACAO_COLETA_AVALIADA,
        'coleta_requisito',
        hash_idempotencia,
        json.dumps(evidencia, ensure_ascii=False, separators=(',', ':')),
    )
    return True


def _payload_evento(evento: AuditoriaEvento) -> dict:
    try:
        conteudo = json.loads(evento.payload_minimo or '{}')
        return conteudo if isinstance(conteudo, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _utc(valor) -> datetime | None:
    if not isinstance(valor, datetime):
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def _arredondar_percentual(numerador: int, denominador: int) -> float | None:
    if denominador <= 0:
        return None
    return round((numerador / denominador) * 100, 2)


def _metricas_acompanhamento_teams(db: Session, *, limite: datetime) -> dict:
    itens = (
        db.query(TeamsNotificationQueueItem)
        .filter(TeamsNotificationQueueItem.origem == 'requisitos')
        .order_by(TeamsNotificationQueueItem.criado_em.asc())
        .all()
    )
    itens = [
        item
        for item in itens
        if (instante := _utc(item.criado_em)) is not None and instante >= limite
    ]

    estados = Counter(item.status_evento for item in itens)
    enviados = estados.get('ENVIADO', 0)
    falhas = estados.get('FALHA', 0)
    conclusivas = enviados + falhas
    latencias = [
        float(item.latencia_ms)
        for item in itens
        if item.status_evento == 'ENVIADO' and isinstance(item.latencia_ms, int)
    ]
    entregas = [
        _utc(item.enviado_em)
        for item in itens
        if item.status_evento == 'ENVIADO' and _utc(item.enviado_em) is not None
    ]

    return {
        'fonte': 'teams_notification_queue',
        'notificacoes_total': len(itens),
        'pendentes': estados.get('PENDENTE', 0),
        'processando': estados.get('PROCESSANDO', 0),
        'enviadas': enviados,
        'falhas': falhas,
        'canceladas': estados.get('CANCELADO', 0),
        'taxa_sucesso_percentual': _arredondar_percentual(enviados, conclusivas),
        'latencia_media_ms': round(mean(latencias), 2) if latencias else None,
        'ultima_entrega_em': max(entregas).isoformat() if entregas else None,
        'deduplicacao': 'coleta + tipo_evento por hash SHA-256',
    }


def calcular_metricas_coleta_requisitos(db: Session, *, janela_dias: int = 30) -> dict:
    """Consolida métricas auditáveis da entrada governada.

    O cálculo usa eventos de auditoria já persistidos. Coleções anteriores à
    implantação da telemetria não são retroativamente estimadas.
    """

    janela = max(1, min(int(janela_dias), 365))
    limite = datetime.now(UTC) - timedelta(days=janela)

    eventos = (
        db.query(AuditoriaEvento)
        .filter(AuditoriaEvento.acao.in_([ACAO_COLETA_AVALIADA, ACAO_REQUISITO_GERADO]))
        .order_by(AuditoriaEvento.criado_em.asc(), AuditoriaEvento.id.asc())
        .all()
    )

    grupos: dict[str, dict] = {}
    avaliacoes_total = 0

    for evento in eventos:
        instante = _utc(evento.criado_em)
        if instante is None or instante < limite:
            continue

        dados = _payload_evento(evento)
        chave = str(dados.get('chave_idempotencia_hash') or '').strip()
        if not chave:
            chave = f'evento:{evento.id}'

        grupo = grupos.setdefault(chave, {'avaliacoes': [], 'geracoes': []})
        item = {'instante': instante, 'dados': dados, 'evento_id': evento.id}
        if evento.acao == ACAO_COLETA_AVALIADA:
            grupo['avaliacoes'].append(item)
            avaliacoes_total += 1
        elif evento.acao == ACAO_REQUISITO_GERADO:
            grupo['geracoes'].append(item)

    primeiras_avaliacoes = []
    ultimas_avaliacoes = []
    grupos_gerados = []
    grupos_em_refinamento = []
    origens = Counter()
    classificacoes = Counter()
    pendencias = Counter()
    tempos_refinamento = []

    for grupo in grupos.values():
        avaliacoes = sorted(
            grupo['avaliacoes'],
            key=lambda item: (item['instante'], item['evento_id']),
        )
        geracoes = sorted(
            grupo['geracoes'],
            key=lambda item: (item['instante'], item['evento_id']),
        )

        primeira = avaliacoes[0] if avaliacoes else None
        ultima = avaliacoes[-1] if avaliacoes else None
        geracao = geracoes[0] if geracoes else None

        if primeira:
            primeiras_avaliacoes.append(primeira)
        if ultima:
            ultimas_avaliacoes.append(ultima)
        if geracao:
            grupos_gerados.append(grupo)

        referencia = ultima or geracao
        if referencia:
            origem = str(referencia['dados'].get('origem') or 'desconhecida')
            origens[origem] += 1

        if ultima:
            classificacao = str(ultima['dados'].get('classificacao') or 'desconhecida')
            classificacoes[classificacao] += 1

        pronto = bool(ultima and ultima['dados'].get('pronto_para_gerar') is True)
        if ultima and not pronto and not geracao:
            grupos_em_refinamento.append(grupo)
            for codigo in ultima['dados'].get('codigos_pendencia') or []:
                pendencias[str(codigo)] += 1

        primeira_pronta = bool(primeira and primeira['dados'].get('pronto_para_gerar') is True)
        if primeira and geracao and not primeira_pronta and geracao['instante'] >= primeira['instante']:
            minutos = (geracao['instante'] - primeira['instante']).total_seconds() / 60
            tempos_refinamento.append(minutos)

    pontuacoes_atuais = [
        float(item['dados']['pontuacao'])
        for item in ultimas_avaliacoes
        if isinstance(item['dados'].get('pontuacao'), (int, float))
    ]
    aprovadas_primeira = sum(
        1 for item in primeiras_avaliacoes if item['dados'].get('pronto_para_gerar') is True
    )
    geradas_com_avaliacao = sum(1 for grupo in grupos_gerados if grupo['avaliacoes'])

    principais_pendencias = [
        {
            'codigo': codigo,
            'rotulo': ROTULOS_PENDENCIA.get(codigo, codigo.replace('_', ' ').title()),
            'quantidade': quantidade,
        }
        for codigo, quantidade in pendencias.most_common(5)
    ]

    return {
        'schema_version': VERSAO_CONTRATO_OBSERVABILIDADE,
        'gerado_em': datetime.now(UTC).isoformat(),
        'janela_dias': janela,
        'sem_dados': len(grupos) == 0,
        'coletas_total': len(grupos),
        'avaliacoes_total': avaliacoes_total,
        'requisitos_gerados': len(grupos_gerados),
        'em_refinamento': len(grupos_em_refinamento),
        'taxa_aprovacao_primeira_submissao_percentual': _arredondar_percentual(
            aprovadas_primeira,
            len(primeiras_avaliacoes),
        ),
        'pontuacao_media_atual': round(mean(pontuacoes_atuais), 2) if pontuacoes_atuais else None,
        'tempo_medio_refinamento_minutos': (
            round(mean(tempos_refinamento), 2) if tempos_refinamento else None
        ),
        'cobertura_avaliacao_das_geracoes_percentual': _arredondar_percentual(
            geradas_com_avaliacao,
            len(grupos_gerados),
        ),
        'origens': [
            {'origem': origem, 'quantidade': quantidade}
            for origem, quantidade in origens.most_common()
        ],
        'classificacoes_atuais': [
            {'classificacao': classificacao, 'quantidade': quantidade}
            for classificacao, quantidade in classificacoes.most_common()
        ],
        'principais_pendencias': principais_pendencias,
        'acompanhamento_teams': _metricas_acompanhamento_teams(db, limite=limite),
        'nota_dados': (
            'Métricas calculadas somente a partir dos eventos de telemetria da coleta governada; '
            'não há retroestimativa para coletas anteriores à implantação.'
        ),
    }
