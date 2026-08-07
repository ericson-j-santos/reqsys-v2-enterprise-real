"""Testes de integracao do card de status de requisito nos payloads do
Teams Messaging Gateway (canais 'webhook' e 'flow_bot')."""

from app.services import teams_gateway as svc


def test_payload_webhook_sem_evento_status_usa_card_generico():
    payload = svc._payload_webhook('Corpo simples', 'text', {'titulo': 'Alerta'})

    card = payload['attachments'][0]['content']
    assert card['version'] == '1.2'
    assert card['body'] == [
        {'type': 'TextBlock', 'size': 'Medium', 'weight': 'Bolder', 'text': 'Alerta'},
        {'type': 'TextBlock', 'text': 'Corpo simples', 'wrap': True},
    ]


def test_payload_webhook_com_evento_status_usa_card_de_status():
    payload = svc._payload_webhook(
        'Descricao ignorada, metadata tem descricao propria',
        'text',
        {
            'evento_status': 'aprovado',
            'titulo': 'Requisito #482 aprovado',
            'descricao': 'Aprovado pelo comite.',
            'propriedades': [{'key': 'Responsavel', 'value': 'Squad X'}],
            'view_url': 'https://reqsys-app.fly.dev/requisitos/482',
        },
    )

    card = payload['attachments'][0]['content']
    assert card['version'] == '1.4'
    assert card['body'][0]['style'] == 'good'
    assert card['actions'] == [
        {'type': 'Action.OpenUrl', 'title': 'Abrir no ReqSys', 'url': 'https://reqsys-app.fly.dev/requisitos/482'}
    ]


def test_payload_webhook_com_evento_status_invalido_cai_para_card_generico():
    payload = svc._payload_webhook('Corpo', 'text', {'evento_status': 'nao_existe', 'titulo': 'X'})

    card = payload['attachments'][0]['content']
    assert card['version'] == '1.2'


def test_payload_flow_bot_sem_evento_status_nao_inclui_adaptive_card():
    payload = svc._payload_flow_bot('fulano@tieri659.onmicrosoft.com', 'Corpo', {'titulo': 'Alerta'}, 'corr-1')

    assert 'adaptiveCard' not in payload


def test_payload_flow_bot_com_evento_status_inclui_adaptive_card():
    payload = svc._payload_flow_bot(
        'fulano@tieri659.onmicrosoft.com',
        'Corpo',
        {
            'evento_status': 'bloqueado',
            'titulo': 'Requisito #455 bloqueado',
            'descricao': 'Aguardando liberacao de acesso externo.',
            'view_url': 'https://reqsys-app.fly.dev/requisitos/455',
        },
        'corr-2',
    )

    assert 'adaptiveCard' in payload
    assert payload['adaptiveCard']['body'][0]['style'] == 'attention'
    assert payload['to'] == 'fulano@tieri659.onmicrosoft.com'
    assert payload['correlationId'] == 'corr-2'
