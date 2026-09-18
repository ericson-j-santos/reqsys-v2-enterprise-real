import asyncio
import json
from types import SimpleNamespace

from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.services import coleta_requisitos_teams
from app.services.coleta_requisitos_observabilidade import calcular_metricas_coleta_requisitos


def _payload():
    return SimpleNamespace(origem='reqsys')


def _avaliacao(pronto=False):
    return SimpleNamespace(
        pontuacao=75 if not pronto else 95,
        classificacao='refinamento' if not pronto else 'ouro',
        pronto_para_gerar=pronto,
        pendencias=['Complementar critérios de aceite'] if not pronto else [],
    )


def _notificar(db_session, *, tipo_evento, pronto=False, requisito=None):
    return asyncio.run(
        coleta_requisitos_teams.notificar_acompanhamento_coleta(
            db_session,
            tipo_evento=tipo_evento,
            payload=_payload(),
            avaliacao=_avaliacao(pronto),
            hash_idempotencia='a' * 64,
            payload_hash='b' * 64,
            correlation_id='corr-coleta-teams-001',
            requisito=requisito,
        )
    )


def test_acompanhamento_teams_deduplica_por_coleta_e_evento(db_session, monkeypatch):
    monkeypatch.setattr(coleta_requisitos_teams, '_webhook_operacional', lambda _db: False)

    primeira = _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_REFINAMENTO,
    )
    repetida = _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_REFINAMENTO,
    )

    assert primeira['id_evento'] == repetida['id_evento']
    assert primeira['status_evento'] == 'PENDENTE'
    assert primeira['deduplicado'] is False
    assert repetida['deduplicado'] is True

    itens = db_session.query(TeamsNotificationQueueItem).all()
    assert len(itens) == 1
    metadata = json.loads(itens[0].metadata_json)
    assert metadata['origem_funcional'] == 'coleta_requisitos'
    assert metadata['dedupe_key_hash']
    assert 'problema' not in metadata
    assert 'objetivo' not in metadata


def test_eventos_distintos_da_mesma_coleta_geram_itens_distintos(db_session, monkeypatch):
    monkeypatch.setattr(coleta_requisitos_teams, '_webhook_operacional', lambda _db: False)

    _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_REFINAMENTO,
    )
    gerado = _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_GERADO,
        pronto=True,
        requisito=SimpleNamespace(codigo='REQ-TESTE-001'),
    )

    itens = db_session.query(TeamsNotificationQueueItem).order_by(
        TeamsNotificationQueueItem.id_evento.asc()
    ).all()
    assert len(itens) == 2
    assert gerado['id_evento'] == itens[1].id_evento
    assert {item.tipo_evento for item in itens} == {
        coleta_requisitos_teams.TIPO_EVENTO_REFINAMENTO,
        coleta_requisitos_teams.TIPO_EVENTO_GERADO,
    }


def test_dashboard_coleta_consome_status_da_fila_central_teams(db_session, monkeypatch):
    monkeypatch.setattr(coleta_requisitos_teams, '_webhook_operacional', lambda _db: False)

    _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_REFINAMENTO,
    )
    _notificar(
        db_session,
        tipo_evento=coleta_requisitos_teams.TIPO_EVENTO_GERADO,
        pronto=True,
        requisito=SimpleNamespace(codigo='REQ-TESTE-002'),
    )

    itens = db_session.query(TeamsNotificationQueueItem).order_by(
        TeamsNotificationQueueItem.id_evento.asc()
    ).all()
    itens[0].status_evento = 'ENVIADO'
    itens[0].latencia_ms = 120
    itens[0].enviado_em = itens[0].criado_em
    itens[1].status_evento = 'FALHA'
    db_session.commit()

    metricas = calcular_metricas_coleta_requisitos(db_session, janela_dias=30)
    teams = metricas['acompanhamento_teams']

    assert teams['fonte'] == 'teams_notification_queue'
    assert teams['notificacoes_total'] == 2
    assert teams['enviadas'] == 1
    assert teams['falhas'] == 1
    assert teams['taxa_sucesso_percentual'] == 50.0
    assert teams['latencia_media_ms'] == 120.0
