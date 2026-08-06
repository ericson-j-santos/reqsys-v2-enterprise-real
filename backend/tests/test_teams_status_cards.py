"""Testes do construtor de Adaptive Cards de status de requisito (Teams)."""

import pytest

from app.services.teams_status_cards import (
    EVENTOS_STATUS_REQUISITO,
    construir_adaptive_card_status_requisito,
)


def test_evento_desconhecido_levanta_value_error():
    with pytest.raises(ValueError, match='evento de status de requisito desconhecido'):
        construir_adaptive_card_status_requisito(
            evento='inexistente', titulo='Titulo', descricao='Descricao'
        )


@pytest.mark.parametrize('evento', sorted(EVENTOS_STATUS_REQUISITO))
def test_cada_evento_conhecido_produz_card_valido(evento):
    card = construir_adaptive_card_status_requisito(
        evento=evento, titulo='Requisito #1 — Teste', descricao='Descricao de teste'
    )

    assert card['type'] == 'AdaptiveCard'
    assert card['$schema'] == 'http://adaptivecards.io/schemas/adaptive-card.json'
    container = card['body'][0]
    assert container['type'] == 'Container'
    assert container['style'] == EVENTOS_STATUS_REQUISITO[evento]['estilo']
    icone_textblock = container['items'][0]['columns'][0]['items'][0]
    assert icone_textblock['text'] == EVENTOS_STATUS_REQUISITO[evento]['icone']


def test_card_sem_status_label_nao_adiciona_segundo_textblock():
    card = construir_adaptive_card_status_requisito(evento='aprovado', titulo='T', descricao='D')

    coluna_texto = card['body'][0]['items'][0]['columns'][1]['items']
    assert len(coluna_texto) == 1


def test_card_com_status_label_adiciona_segundo_textblock():
    card = construir_adaptive_card_status_requisito(
        evento='aprovado', titulo='T', descricao='D', status_label='Aprovado hoje'
    )

    coluna_texto = card['body'][0]['items'][0]['columns'][1]['items']
    assert len(coluna_texto) == 2
    assert coluna_texto[1]['text'] == 'Aprovado hoje'


def test_card_sem_propriedades_nao_tem_factset():
    card = construir_adaptive_card_status_requisito(evento='aprovado', titulo='T', descricao='D')

    tipos = [item['type'] for item in card['body']]
    assert 'FactSet' not in tipos


def test_card_com_propriedades_monta_factset():
    card = construir_adaptive_card_status_requisito(
        evento='bloqueado',
        titulo='T',
        descricao='D',
        propriedades=[{'key': 'Responsavel', 'value': 'Squad X'}],
    )

    factset = next(item for item in card['body'] if item['type'] == 'FactSet')
    assert factset['facts'] == [{'title': 'Responsavel:', 'value': 'Squad X'}]


def test_card_sem_view_url_nao_tem_actions():
    card = construir_adaptive_card_status_requisito(evento='concluido', titulo='T', descricao='D')

    assert 'actions' not in card


def test_card_com_view_url_monta_action_open_url():
    card = construir_adaptive_card_status_requisito(
        evento='concluido', titulo='T', descricao='D', view_url='https://reqsys-app.fly.dev/requisitos/1'
    )

    assert card['actions'] == [
        {
            'type': 'Action.OpenUrl',
            'title': 'Abrir no ReqSys',
            'url': 'https://reqsys-app.fly.dev/requisitos/1',
        }
    ]
