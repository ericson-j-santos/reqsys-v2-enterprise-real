from pathlib import Path


def main() -> None:
    gateway_path = Path('backend/app/services/teams_gateway.py')
    text = gateway_path.read_text(encoding='utf-8')

    old_imports = "import logging\nimport uuid\nfrom typing import Any\n"
    new_imports = "import json\nimport logging\nimport os\nimport uuid\nfrom datetime import datetime, timezone\nfrom typing import Any\n"
    if old_imports not in text:
        raise SystemExit('Bloco de imports esperado não encontrado.')
    text = text.replace(old_imports, new_imports, 1)

    old_sender = '''async def _enviar_webhook(url: str, texto: str, content_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    payload = _payload_webhook(texto, content_type, metadata)

    async def _postar() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return {'status_code': resp.status_code}

    return await call_with_retry_async(
        _postar,
        max_retries=_WEBHOOK_MAX_RETRIES,
        backoff_seconds=_WEBHOOK_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=_webhook_circuit,
    )
'''
    new_sender = '''def _payload_power_automate_webhook(
    texto: str,
    content_type: str,
    metadata: dict[str, Any],
    *,
    correlation_id: str,
    recipient: str,
) -> dict[str, Any]:
    title = metadata.get('titulo') or metadata.get('title') or 'ReqSys Teams Gateway'
    content = texto if content_type == 'text' else texto.replace('<br>', '\\n')
    card = _adaptive_card_de_metadata(metadata, content)
    if card is None:
        card = {
            '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
            'type': 'AdaptiveCard',
            'version': '1.2',
            'body': [
                {'type': 'TextBlock', 'size': 'Medium', 'weight': 'Bolder', 'text': title},
                {'type': 'TextBlock', 'text': content, 'wrap': True},
            ],
        }

    try:
        provider_correlation = str(uuid.UUID(correlation_id))
    except (ValueError, AttributeError, TypeError):
        provider_correlation = str(uuid.uuid5(uuid.NAMESPACE_URL, f'reqsys:{correlation_id}'))

    event_type = (
        metadata.get('notification_type')
        or metadata.get('event_type')
        or metadata.get('evento_status')
        or 'reqsys-notification'
    )
    return {
        'to': recipient,
        'title': str(title),
        'content': content,
        'signature': 'ReqSys',
        'stampDate': datetime.now(timezone.utc).isoformat(),
        'correlationId': provider_correlation,
        'eventType': str(event_type),
        'renderMode': 'adaptive-card',
        'adaptiveCard': card,
        'adaptiveCardJson': json.dumps(card, ensure_ascii=False, separators=(',', ':')),
    }


async def _enviar_webhook(
    url: str,
    texto: str,
    content_type: str,
    metadata: dict[str, Any],
    *,
    correlation_id: str,
    power_automate_recipient: str | None = None,
) -> dict[str, Any]:
    if power_automate_recipient:
        payload = _payload_power_automate_webhook(
            texto,
            content_type,
            metadata,
            correlation_id=correlation_id,
            recipient=power_automate_recipient,
        )
    else:
        payload = _payload_webhook(texto, content_type, metadata)

    async def _postar() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={'X-Correlation-ID': correlation_id},
            )
            resp.raise_for_status()
            return {'status_code': resp.status_code}

    return await call_with_retry_async(
        _postar,
        max_retries=_WEBHOOK_MAX_RETRIES,
        backoff_seconds=_WEBHOOK_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=_webhook_circuit,
    )
'''
    if old_sender not in text:
        raise SystemExit('Função _enviar_webhook esperada não encontrada.')
    text = text.replace(old_sender, new_sender, 1)

    old_call = "        provider = await _enviar_webhook(url, request.texto, request.content_type, request.metadata)\n"
    new_call = '''        # URLs explícitas continuam usando o contrato Incoming Webhook.
        # A URL global governada aponta para o fluxo Power Automate validado em DEV.
        power_automate_recipient = None
        if not request.webhook_url:
            power_automate_recipient = os.getenv('TEAMS_WEBHOOK_RECIPIENT', '').strip() or None
        provider = await _enviar_webhook(
            url,
            request.texto,
            request.content_type,
            request.metadata,
            correlation_id=correlation_id,
            power_automate_recipient=power_automate_recipient,
        )
'''
    if old_call not in text:
        raise SystemExit('Chamada _enviar_webhook esperada não encontrada.')
    gateway_path.write_text(text.replace(old_call, new_call, 1), encoding='utf-8')

    tests_path = Path('backend/tests/test_teams_gateway_service.py')
    tests = tests_path.read_text(encoding='utf-8')
    if 'test_payload_power_automate_respeita_contrato_validado' in tests:
        raise SystemExit('Testes contratuais já presentes; abortando duplicação.')
    tests = tests.replace('import asyncio\n', 'import asyncio\nimport uuid\n', 1)
    tests += r'''

@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
def test_webhook_global_usa_contrato_power_automate_com_destinatario(mock_webhook, monkeypatch):
    mock_webhook.return_value = {'status_code': 200}
    monkeypatch.setattr(svc.settings, 'teams_notifications_webhook_url', 'https://example.invalid/power-automate')
    monkeypatch.setenv('TEAMS_WEBHOOK_RECIPIENT', 'destino@example.invalid')
    payload = TeamsGatewayMessageRequest(
        destino_tipo='canal',
        modo='webhook',
        texto='Evento governado',
        metadata={'titulo': 'ReqSys', 'notification_type': 'coleta_requisito_gerado'},
    )
    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-power-automate'))
    assert resultado['entregue'] is True
    kwargs = mock_webhook.await_args.kwargs
    assert kwargs['correlation_id'] == 'corr-power-automate'
    assert kwargs['power_automate_recipient'] == 'destino@example.invalid'


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
def test_webhook_explicito_preserva_contrato_incoming_webhook(mock_webhook, monkeypatch):
    mock_webhook.return_value = {'status_code': 202}
    monkeypatch.setenv('TEAMS_WEBHOOK_RECIPIENT', 'destino@example.invalid')
    payload = TeamsGatewayMessageRequest(
        destino_tipo='canal',
        modo='webhook',
        webhook_url='https://example.invalid/incoming-webhook',
        texto='Evento explícito',
    )
    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-explicito'))
    assert resultado['entregue'] is True
    kwargs = mock_webhook.await_args.kwargs
    assert kwargs['correlation_id'] == 'corr-explicito'
    assert kwargs['power_automate_recipient'] is None


def test_payload_power_automate_respeita_contrato_validado():
    payload = svc._payload_power_automate_webhook(
        'Conteúdo',
        'text',
        {'titulo': 'Título', 'notification_type': 'coleta_requisito_refinamento'},
        correlation_id='correlacao-nao-uuid',
        recipient='destino@example.invalid',
    )
    assert payload['to'] == 'destino@example.invalid'
    assert payload['title'] == 'Título'
    assert payload['content'] == 'Conteúdo'
    assert payload['signature'] == 'ReqSys'
    assert payload['eventType'] == 'coleta_requisito_refinamento'
    assert payload['renderMode'] == 'adaptive-card'
    assert payload['adaptiveCard']['type'] == 'AdaptiveCard'
    assert payload['adaptiveCardJson'].startswith('{')
    assert str(uuid.UUID(payload['correlationId'])) == payload['correlationId']
'''
    tests_path.write_text(tests, encoding='utf-8')


if __name__ == '__main__':
    main()
