def test_govbi_status_autenticado(client, auth_headers):
    resp = client.get('/api/govbi/status', headers=auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'ok'
    assert payload['data']['modo'] == 'proxy_governado'
    assert payload['data']['timeout_ms'] >= 1000


def test_govbi_perguntas_retorna_fallback_governado_quando_provider_falha(client, auth_headers):
    resp = client.post(
        '/api/govbi/perguntas',
        headers={**auth_headers, 'X-Correlation-Id': 'corr-govbi-test-001'},
        json={
            'pergunta': 'Quantas propostas por mês em 2024?',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    assert payload['meta']['correlation_id'] == 'corr-govbi-test-001'
    assert payload['data']['statusFluxo'] in {'CONCLUIDO', 'MODO_DEGRADADO'}
    assert payload['data']['resultado']['colunas']
    assert payload['data']['correlationId'] == 'corr-govbi-test-001'
