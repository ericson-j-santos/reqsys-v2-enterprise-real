from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.requisitos import _montar_workflow_state, _validar_transicao
from app.schemas.requisito import RequisitoTransicaoCriar


def requisito(status='recebido', descricao=None):
    return SimpleNamespace(
        id=1,
        codigo='REQ-000000001',
        titulo='Requisito de teste',
        descricao=descricao or 'Como analista, quero registrar requisito. Critério: deve possuir aceite verificável.',
        urgencia='media',
        area='negocio',
        sistema='reqsys',
        solicitante='qa.reqsys',
        status=status,
        impacto_regulatorio=False,
    )


def payload(novo_status, evidencia=None):
    return RequisitoTransicaoCriar(
        novo_status=novo_status,
        usuario='qa.reqsys',
        motivo='Validacao automatizada do workflow governado.',
        evidencia=evidencia,
    )


def test_workflow_state_expõe_transicoes_permitidas_para_estado_recebido():
    estado = _montar_workflow_state(requisito(status='recebido'))

    assert estado['estado_atual'] == 'recebido'
    assert estado['proximo_estado_sugerido'] == 'refinamento'
    assert 'refinamento' in estado['transicoes_permitidas']
    assert estado['estado_terminal'] is False


def test_valida_transicao_permitida_para_refinamento():
    origem, destino = _validar_transicao(requisito(status='recebido'), payload('refinamento'))

    assert origem == 'recebido'
    assert destino == 'refinamento'


def test_bloqueia_transicao_fora_da_maquina_de_estados():
    with pytest.raises(HTTPException) as exc:
        _validar_transicao(requisito(status='recebido'), payload('exportado', evidencia='Evidencia final.'))

    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'TRANSICAO_INVALIDA'


def test_exige_criterio_de_aceite_para_pronto_para_aprovacao():
    req = requisito(status='refinamento', descricao='Descricao sem aceite estruturado nem BDD explicito.')

    with pytest.raises(HTTPException) as exc:
        _validar_transicao(req, payload('pronto_para_aprovacao'))

    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'CRITERIO_ACEITE_OBRIGATORIO'


def test_exige_evidencia_para_exportado():
    with pytest.raises(HTTPException) as exc:
        _validar_transicao(requisito(status='evidenciado'), payload('exportado'))

    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'EVIDENCIA_OBRIGATORIA'


def test_estado_terminal_exportado_nao_permite_nova_transicao():
    with pytest.raises(HTTPException) as exc:
        _validar_transicao(requisito(status='exportado'), payload('refinamento'))

    assert exc.value.status_code == 409
    assert exc.value.detail['code'] == 'REQUISITO_ESTADO_TERMINAL'
