from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services import redmine_lifecycle_batch as batch
from app.services.redmine_lifecycle_sync import RedmineLifecycleSyncError

AGORA = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)


def _requisito(db_session, *, codigo: str, issue_id: int | str | None = 9001) -> Requisito:
    requisito = Requisito(
        codigo=codigo,
        titulo='Reconciliação em lote ReqSys Redmine',
        descricao='Critério de aceite: lote com lock, backoff e quarentena auditável.',
        urgencia='alta',
        area='Engenharia',
        sistema='ReqSys',
        solicitante='teste@reqsys.local',
        status='em_execucao',
        impacto_regulatorio=False,
    )
    db_session.add(requisito)
    db_session.flush()
    if issue_id is not None:
        db_session.add(
            VinculoGit(
                requisito_codigo=requisito.codigo,
                requisito_id=requisito.id,
                tipo='issue',
                provedor='redmine',
                repo='redmine',
                referencia=str(issue_id),
                url=f'https://redmine.example/issues/{issue_id}',
                titulo=f'Redmine issue #{issue_id}',
                autor='tester',
            )
        )
    db_session.commit()
    db_session.refresh(requisito)
    return requisito


def _control(db_session, requisito: Requisito, issue_id: int = 9001) -> dict:
    links = batch._control_links(db_session, requisito, issue_id)
    assert links, 'estado de controle não encontrado'
    return json.loads(links[0].titulo)


def _acoes(db_session) -> list[str]:
    return [evento.acao for evento in db_session.query(AuditoriaEvento).all()]


def test_lote_sincroniza_e_repeticao_nao_produz_nova_mutacao(db_session, monkeypatch):
    requisito = _requisito(db_session, codigo='REQ-168620001')
    chamadas: list[str] = []

    def fake_sync(_db, *, requisito, correlation_id, actor, dry_run):
        chamadas.append(correlation_id)
        return {'codigo': requisito.codigo, 'mutation_count': 1 if len(chamadas) == 1 else 0}

    monkeypatch.setattr(batch, 'sincronizar_requisito_redmine', fake_sync)

    primeiro = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-lote-1',
        actor='service-token:redmine-sync',
        agora=AGORA,
    )

    assert primeiro['avaliados'] == 1
    assert primeiro['contagens'] == {batch.OUTCOME_SYNCED: 1}
    assert primeiro['mutation_count'] == 1
    assert primeiro['itens'][0]['redmine_issue_id'] == 9001
    assert chamadas == ['corr-lote-1:REQ-168620001']

    controle = _control(db_session, requisito)
    assert controle['lock'] is None
    assert controle['attempts'] == 0
    assert controle['last_success_at'] == '2026-09-17T12:00:00Z'

    segundo = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-lote-2',
        actor='service-token:redmine-sync',
        agora=AGORA + timedelta(minutes=1),
    )

    # Idempotência: mesma entrada, nenhuma mutação adicional.
    assert segundo['contagens'] == {batch.OUTCOME_SYNCED: 1}
    assert segundo['mutation_count'] == 0
    assert len(chamadas) == 2


def test_lock_impede_processamento_simultaneo_do_mesmo_requisito(db_session, monkeypatch):
    requisito = _requisito(db_session, codigo='REQ-168620002')
    concorrente: dict[str, object] = {}

    def fake_sync(_db, *, requisito, correlation_id, actor, dry_run):
        # Segundo worker tenta o mesmo requisito enquanto o lock está ativo.
        concorrente['resultado'] = batch.reconciliar_requisito(
            db_session,
            requisito=requisito,
            correlation_id='corr-worker-b',
            actor='service-token:redmine-sync',
            worker_id='worker-b',
            agora=AGORA,
        )
        return {'codigo': requisito.codigo, 'mutation_count': 1}

    monkeypatch.setattr(batch, 'sincronizar_requisito_redmine', fake_sync)

    resultado = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-worker-a',
        actor='service-token:redmine-sync',
        worker_id='worker-a',
        agora=AGORA,
    )

    assert resultado['outcome'] == batch.OUTCOME_SYNCED
    segundo = concorrente['resultado']
    assert segundo['outcome'] == batch.OUTCOME_SKIPPED_LOCK
    assert segundo['lock_owner'] == 'worker-a'
    # Lock liberado ao final do processamento do primeiro worker.
    assert _control(db_session, requisito)['lock'] is None


def test_lock_expirado_e_assumido_pelo_proximo_worker(db_session, monkeypatch):
    requisito = _requisito(db_session, codigo='REQ-168620003')
    monkeypatch.setattr(
        batch,
        'sincronizar_requisito_redmine',
        lambda _db, **kwargs: {'codigo': kwargs['requisito'].codigo, 'mutation_count': 0},
    )

    control_link = batch._ensure_control_link(
        db_session,
        requisito,
        issue_id=9001,
        issue_url=None,
        actor='tester',
    )
    expirado = {
        **batch._empty_control(),
        'lock': {
            'owner': 'worker-morto',
            'correlation_id': 'corr-antiga',
            'acquired_at': '2026-09-17T11:00:00Z',
            'expires_at': '2026-09-17T11:10:00Z',
        },
    }
    control_link.titulo = batch._dump(expirado)
    db_session.add(control_link)
    db_session.commit()

    resultado = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-worker-novo',
        actor='service-token:redmine-sync',
        worker_id='worker-novo',
        agora=AGORA,
    )

    assert resultado['outcome'] == batch.OUTCOME_SYNCED


def test_falha_aplica_backoff_depois_quarentena_e_liberacao_explicita(db_session, monkeypatch):
    requisito = _requisito(db_session, codigo='REQ-168620004')
    falhas = {'ativa': True}

    def fake_sync(_db, **_kwargs):
        if falhas['ativa']:
            raise RedmineLifecycleSyncError('conflito de propriedade de campo')
        return {'codigo': requisito.codigo, 'mutation_count': 0}

    monkeypatch.setattr(batch, 'sincronizar_requisito_redmine', fake_sync)

    comuns = {
        'actor': 'service-token:redmine-sync',
        'max_tentativas': 2,
        'backoff_base_minutos': 5,
        'backoff_max_minutos': 240,
    }

    primeira = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-falha-1',
        agora=AGORA,
        **comuns,
    )
    assert primeira['outcome'] == batch.OUTCOME_FAILED
    assert primeira['attempts'] == 1
    assert primeira['backoff_minutos'] == 5
    assert primeira['next_attempt_at'] == '2026-09-17T12:05:00Z'
    assert 'REDMINE_SYNC_FALHA' in _acoes(db_session)

    # Dentro da janela de backoff o requisito não é reprocessado.
    durante_backoff = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-falha-2',
        agora=AGORA + timedelta(minutes=1),
        **comuns,
    )
    assert durante_backoff['outcome'] == batch.OUTCOME_SKIPPED_BACKOFF

    segunda = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-falha-3',
        agora=AGORA + timedelta(minutes=10),
        **comuns,
    )
    assert segunda['outcome'] == batch.OUTCOME_QUARANTINED
    assert segunda['attempts'] == 2
    assert segunda['next_attempt_at'] is None
    assert 'REDMINE_SYNC_QUARENTENA' in _acoes(db_session)

    controle = _control(db_session, requisito)
    assert controle['quarantined'] is True
    assert controle['quarantine_reason'] == 'conflito de propriedade de campo'
    assert controle['lock'] is None

    # Em quarentena o requisito sai do lote até liberação explícita.
    em_quarentena = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-falha-4',
        agora=AGORA + timedelta(hours=8),
        **comuns,
    )
    assert em_quarentena['outcome'] == batch.OUTCOME_SKIPPED_QUARANTINE

    falhas['ativa'] = False
    liberacao = batch.liberar_quarentena(
        db_session,
        requisito=requisito,
        correlation_id='corr-liberacao',
        actor='admin@reqsys.local',
        agora=AGORA + timedelta(hours=9),
    )
    assert liberacao['released'] is True
    assert liberacao['quarantine_reason_anterior'] == 'conflito de propriedade de campo'
    assert 'REDMINE_SYNC_QUARENTENA_LIBERADA' in _acoes(db_session)

    apos_liberacao = batch.reconciliar_requisito(
        db_session,
        requisito=requisito,
        correlation_id='corr-pos-liberacao',
        agora=AGORA + timedelta(hours=9, minutes=1),
        **comuns,
    )
    assert apos_liberacao['outcome'] == batch.OUTCOME_SYNCED
    assert _control(db_session, requisito)['quarantined'] is False


def test_liberar_quarentena_sem_quarentena_nao_muta(db_session):
    requisito = _requisito(db_session, codigo='REQ-168620005')
    batch._ensure_control_link(
        db_session,
        requisito,
        issue_id=9001,
        issue_url=None,
        actor='tester',
    )

    resultado = batch.liberar_quarentena(
        db_session,
        requisito=requisito,
        correlation_id='corr-liberacao-noop',
        actor='admin@reqsys.local',
        agora=AGORA,
    )

    assert resultado['released'] is False
    assert resultado['reason'] == 'nao_estava_em_quarentena'
    assert 'REDMINE_SYNC_QUARENTENA_LIBERADA' not in _acoes(db_session)


def test_dry_run_nao_chama_sync_nem_cria_estado_de_controle(db_session, monkeypatch):
    requisito = _requisito(db_session, codigo='REQ-168620006')

    def nunca(*_args, **_kwargs):  # pragma: no cover - deve permanecer não chamado
        raise AssertionError('dry-run não pode acionar sincronização real')

    monkeypatch.setattr(batch, 'sincronizar_requisito_redmine', nunca)

    resultado = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-dry-run',
        actor='service-token:redmine-sync',
        dry_run=True,
        agora=AGORA,
    )

    assert resultado['dry_run'] is True
    assert resultado['contagens'] == {batch.OUTCOME_DRY_RUN: 1}
    assert resultado['mutation_count'] == 0
    assert resultado['itens'][0]['would_process'] is True
    assert batch._control_links(db_session, requisito, 9001) == []


def test_requisito_sem_vinculo_ou_com_vinculo_invalido_falha_fechado(db_session, monkeypatch):
    monkeypatch.setattr(
        batch,
        'sincronizar_requisito_redmine',
        lambda *_args, **_kwargs: pytest.fail('não deve sincronizar sem vínculo válido'),
    )

    sem_vinculo = _requisito(db_session, codigo='REQ-168620007', issue_id=None)
    resultado_sem = batch.reconciliar_requisito(
        db_session,
        requisito=sem_vinculo,
        correlation_id='corr-sem-vinculo',
        actor='service-token:redmine-sync',
        agora=AGORA,
    )
    assert resultado_sem['outcome'] == batch.OUTCOME_FAILED
    assert 'vínculo' in resultado_sem['error']

    invalido = _requisito(db_session, codigo='REQ-168620008', issue_id='nao-numerico')
    resultado_invalido = batch.reconciliar_requisito(
        db_session,
        requisito=invalido,
        correlation_id='corr-vinculo-invalido',
        actor='service-token:redmine-sync',
        agora=AGORA,
    )
    assert resultado_invalido['outcome'] == batch.OUTCOME_FAILED

    # Lote só considera requisitos com vínculo de issue Redmine.
    lote = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-lote-sem-vinculo',
        actor='service-token:redmine-sync',
        dry_run=True,
        agora=AGORA,
    )
    codigos = {item['codigo'] for item in lote['itens']}
    assert 'REQ-168620007' not in codigos
    assert 'REQ-168620008' in codigos


def test_lote_respeita_limite_e_selecao_explicita(db_session, monkeypatch):
    primeiro = _requisito(db_session, codigo='REQ-168620009', issue_id=9101)
    segundo = _requisito(db_session, codigo='REQ-168620010', issue_id=9102)
    monkeypatch.setattr(
        batch,
        'sincronizar_requisito_redmine',
        lambda _db, **kwargs: {'codigo': kwargs['requisito'].codigo, 'mutation_count': 0},
    )

    limitado = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-limite',
        actor='service-token:redmine-sync',
        lote_max=1,
        agora=AGORA,
    )
    assert limitado['avaliados'] == 1
    assert limitado['itens'][0]['codigo'] == primeiro.codigo

    explicito = batch.reconciliar_lote(
        db_session,
        correlation_id='corr-explicito',
        actor='service-token:redmine-sync',
        requisito_ids=[segundo.id],
        agora=AGORA,
    )
    assert [item['codigo'] for item in explicito['itens']] == [segundo.codigo]


def test_backoff_exponencial_com_teto():
    assert batch._backoff_minutos(1, base_minutos=5, max_minutos=240) == 5
    assert batch._backoff_minutos(2, base_minutos=5, max_minutos=240) == 10
    assert batch._backoff_minutos(3, base_minutos=5, max_minutos=240) == 20
    assert batch._backoff_minutos(9, base_minutos=5, max_minutos=240) == 240
