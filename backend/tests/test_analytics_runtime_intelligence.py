from app.api.analytics_runtime_intelligence import _calcular_health_score, _snapshot_ari, _validacoes_base


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
    assert data['draft_recomendado'] is True
    assert data['production_ready'] is False
    assert len(data['readiness_matrix']) >= 10
    assert len(data['production_gaps']) >= 7
    assert len(data['runtime_timeline']) >= 6

    codigos = {item['codigo'] for item in data['validacoes']}
    assert 'JOIN_CARDINALITY' in codigos
    assert 'AI_GROUNDING' in codigos
    assert any(gate['acao'] == 'BLOCK' for gate in data['guard_rails'])
    assert data['figma']['status'] == 'aguardando_plano_figma'


def test_ari_validacoes_base_contem_scores_e_status_operacionais():
    validacoes = _validacoes_base()

    assert len(validacoes) == 10
    assert all(0 <= item['score'] <= 100 for item in validacoes)
    assert {item['status'] for item in validacoes}.issubset({'ok', 'warn', 'fail', 'block'})
    assert _calcular_health_score(validacoes) == 92


def test_ari_snapshot_tem_guard_rails_e_figma_pendente_com_evidencia_real():
    snapshot = _snapshot_ari()

    assert snapshot['health_score'] == 92
    assert snapshot['figma']['status'] == 'aguardando_plano_figma'
    assert len(snapshot['guard_rails']) >= 6
    assert {'regra': 'IA sem fonte ou sem grounding', 'acao': 'BLOCK'} in snapshot['guard_rails']


def test_ari_readiness_layer_explica_gaps_e_bloqueios_operacionais():
    snapshot = _snapshot_ari()
    bloqueios = [item for item in snapshot['readiness_matrix'] if item['bloqueia_producao']]
    estados = {item['estado'] for item in snapshot['readiness_matrix']}

    assert bloqueios
    assert 'BLOQUEIO' in estados
    assert 'EVIDENCIA AUSENTE' in estados
    assert 'Validar ARI Center em staging publicado.' in snapshot['production_gaps']
    assert snapshot['runtime_timeline'][-1]['estado'] == 'PENDENTE'
