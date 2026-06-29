def test_connectors_health_retorna_contrato(client):
    resp = client.get('/api/connectors/health', headers={'X-Correlation-ID': 'conn-test-1'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    data = payload['data']
    assert data['correlation_id'] == 'conn-test-1'
    assert len(data['conectores']) >= 4
    assert data['resumo']['total'] == len(data['conectores'])
    assert data['resumo']['estado_geral'] in {'verde', 'amarelo', 'bloqueado'}
    primeiro = data['conectores'][0]
    assert {'ambiente', 'conector', 'capability', 'status', 'criticidade', 'acao_sugerida'} <= set(primeiro.keys())
