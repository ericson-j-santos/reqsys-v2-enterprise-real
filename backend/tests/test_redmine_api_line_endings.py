"""Regressão do readback CRLF; transporte simulado não substitui E2E externo."""
from __future__ import annotations

import builtins
import copy
import re
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services import redmine_lifecycle_sync as sync
from app.services.redmine_api import montar_campos_requisito_redmine


def _campos(descricao: str) -> dict:
    return {
        'codigo': 'REQ-E2E-1234ABCD',
        'titulo': 'Atualizado 1234ABCD',
        'descricao': descricao,
        'urgencia': 'media',
        'area': 'Engenharia',
        'sistema': 'ReqSys',
        'solicitante': 'E2E automatizado',
        'status': 'recebido',
        'impacto_regulatorio': False,
    }


@pytest.mark.parametrize('text', [
    '', 'sem quebra', 'a\nb', 'a\r\nb', 'a\rb',
    '\r\n\r\n', 'a\r\nb\nc\rd', '  início \t\n  fim  ',
    'ação\u2028não é LF\u2029fim', 'a\n\nb\n', '\r\r\n\n',
])
def test_payload_usa_crlf_sem_perder_conteudo_ou_espacos(text):
    req = SimpleNamespace(**_campos(text))
    before = vars(req).copy()
    fields = montar_campos_requisito_redmine(req)
    expected_body = re.sub(r'\r\n|\n|\r', '\r\n', text)
    expected_prefix = (
        'h2. REQ-E2E-1234ABCD — Atualizado 1234ABCD\r\n\r\n'
        '*Sistema:* ReqSys\r\n'
        '*Área:* Engenharia\r\n'
        '*Solicitante:* E2E automatizado\r\n'
        '*Urgência:* Normal\r\n'
        '*Impacto Regulatório:* Não\r\n\r\n'
        '---\r\n\r\n'
    )
    assert fields == {
        'subject': '[REQ-E2E-1234ABCD] Atualizado 1234ABCD',
        'description': expected_prefix + expected_body,
    }
    assert fields['description'] == re.sub(r'\r\n|\n|\r', '\r\n', fields['description'])
    assert vars(req) == before
    for _ in range(5):
        assert montar_campos_requisito_redmine(req) == fields


def test_reproduz_comprimento_exato_do_e2e_194_para_204():
    fields = montar_campos_requisito_redmine(
        SimpleNamespace(**_campos('Descrição atualizada 1234ABCD'))
    )
    assert len(fields['description']) == 204
    assert fields['description'].count('\r\n') == 10
    assert len(fields['description'].replace('\r\n', '\n')) == 194


def _preparar(db, monkeypatch, corruption=None):
    req = Requisito(**_campos('Descrição \n  segunda\r\nterceira\rfim  '))
    db.add(req)
    db.flush()
    db.add(VinculoGit(
        requisito_codigo=req.codigo, requisito_id=req.id, tipo='issue',
        provedor='redmine', repo='redmine', referencia='9001',
        url='https://redmine.example/issues/9001', titulo='teste CRLF', autor='tester',
    ))
    db.commit()
    db.refresh(req)
    remote = {
        'id': 9001, 'subject': 'antigo', 'description': 'antiga',
        'status': {'id': 2, 'name': 'In Progress'}, 'done_ratio': 40,
        'journals': [],
    }
    writes = []

    def put(issue_id, campos):
        assert issue_id == 9001
        writes.append(copy.deepcopy(campos))
        remote.update(campos)
        # Equivalente independente do setter upstream; nunca ecoar o payload cru.
        remote['description'] = re.sub(r'\r\n|\n|\r', '\r\n', remote['description'])
        if corruption is not None:
            corruption(remote)
        return campos

    monkeypatch.setattr(sync, 'atualizar_issue_redmine', put)
    monkeypatch.setattr(
        sync, 'obter_issue_redmine', lambda *_a, **_k: copy.deepcopy(remote),
    )
    return req, remote, writes


def test_reconciliacao_com_setter_crlf_e_replay_sem_mutacoes(db_session, monkeypatch):
    req, remote, writes = _preparar(db_session, monkeypatch)
    first = sync.sincronizar_requisito_redmine(
        db_session, requisito=req, correlation_id='crlf:first', actor='tester',
    )
    assert first['reqsys_to_redmine']['applied'] is True
    assert remote['description'] == montar_campos_requisito_redmine(req)['description']
    count = db_session.query(AuditoriaEvento).count()
    checkpoint = db_session.query(VinculoGit).filter(
        VinculoGit.tipo == sync.SYNC_STATE_TYPE,
    ).one().titulo
    # Mudar apenas a representação local das quebras não deve causar novo PUT.
    req.descricao = re.sub(r'\r\n|\n|\r', '\r\n', req.descricao)
    db_session.commit()
    for attempt in range(3):
        result = sync.sincronizar_requisito_redmine(
            db_session, requisito=req, correlation_id=f'crlf:replay:{attempt}', actor='tester',
        )
        assert result['mutation_count'] == 0
        assert result['reqsys_to_redmine']['planned'] is False
    assert len(writes) == 1
    assert db_session.query(AuditoriaEvento).count() == count
    assert db_session.query(VinculoGit).filter(
        VinculoGit.tipo == sync.SYNC_STATE_TYPE,
    ).one().titulo == checkpoint


@pytest.mark.parametrize('kind', ['space', 'content', 'blank_line', 'subject'])
def test_readback_continua_rejeitando_divergencia_real(db_session, monkeypatch, kind):
    def corrupt(remote):
        if kind == 'subject':
            remote['subject'] += ' '
        elif kind == 'space':
            remote['description'] += ' '
        elif kind == 'content':
            remote['description'] = remote['description'].replace('Descrição', 'ALTERADO')
        else:
            remote['description'] = remote['description'].replace('\r\n\r\n', '\r\n', 1)

    req, _remote, writes = _preparar(db_session, monkeypatch, corrupt)
    with pytest.raises(sync.RedmineLifecycleSyncError, match='leitura independente'):
        sync.sincronizar_requisito_redmine(
            db_session, requisito=req, correlation_id=f'crlf:negative:{kind}', actor='tester',
        )
    assert len(writes) == 1
    assert db_session.query(AuditoriaEvento).count() == 0
    assert db_session.query(VinculoGit).filter(
        VinculoGit.tipo == sync.SYNC_STATE_TYPE,
    ).count() == 0


def test_fixture_so_carrega_api_real_quando_cliente_e_solicitado(monkeypatch):
    original_import = builtins.__import__
    attempts = []

    def observe_import(name, *args, **kwargs):
        if name == 'app.main':
            attempts.append(name)
            raise ImportError('API_STARTUP_REQUESTED_BY_HTTP_FIXTURE')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', observe_import)
    namespace = runpy.run_path(str(Path(__file__).with_name('conftest.py')))
    assert attempts == []
    fixture = namespace['client'].__wrapped__()
    with pytest.raises(ImportError, match='API_STARTUP_REQUESTED_BY_HTTP_FIXTURE'):
        next(fixture)
    assert attempts == ['app.main']
