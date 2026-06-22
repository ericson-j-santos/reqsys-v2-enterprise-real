def test_analytics_runtime_intelligence_snapshot(client):
    resp = client.get('/v1/analytics-runtime-intelligence/snapshot')

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True

    data = payload['data']
    assert data['capability'] == 'Analytics Runtime Intelligence'
    assert data['posicao_estrategica'] == 'Plataforma enterprise de inteligencia operacional auditavel'
    assert 0 <= data['health_score'] <= 100
    assert 0 <= data['confidence_score'] <= 100
    assert len(data['validacoes']) == 10

    codigos = {item['codigo'] for item in data['validacoes']}
    assert 'JOIN_CARDINALITY' in codigos
    assert 'AI_GROUNDING' in codigos
    assert any(gate['acao'] == 'BLOCK' for gate in data['guard_rails'])
    assert data['figma']['status'] == 'design_operacional_publicado'
