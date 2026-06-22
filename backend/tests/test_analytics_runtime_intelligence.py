from app.api.analytics_runtime_intelligence import _calcular_health_score, _snapshot_ari, _validacoes_base
from app.services.ari_runtime_sql_adapter import AriRuntimeSqlAdapter
from app.services.ari_staging_validator import AriStagingValidator


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
    assert data['runtime_sql_validation']['runtime_sql_ready'] is True
    assert data['staging_validation']['staging_ready'] is False

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
    assert 'EVIDENCIA_AUSENTE' in {item['estado'] for item in snapshot['staging_validation']['checks']}
    assert 'Publicar ambiente e informar URL.' in snapshot['production_gaps']
    assert snapshot['runtime_timeline'][-1]['estado'] == 'PARCIAL'


def test_runtime_sql_adapter_valida_consulta_com_baseline_inicial():
    sql = 'select count(*) total, status from requisitos where status is not null group by status'
    result = AriRuntimeSqlAdapter().validate(sql, null_critical=0)

    assert result['runtime_sql_ready'] is True
    assert result['runtime_sql_score'] >= 90
    assert not result['blockers']


def test_runtime_sql_adapter_bloqueia_null_critico():
    result = AriRuntimeSqlAdapter().validate('select * from requisitos', null_critical=2)

    assert result['runtime_sql_ready'] is False
    assert any(item['regra'] == 'NULL_CRITICAL' for item in result['blockers'])


def test_staging_validator_exige_url_screenshot_e_smoke():
    result = AriStagingValidator().validate()

    assert result['staging_ready'] is False
    assert len(result['blockers']) == 3


def test_staging_validator_aprova_quando_evidencias_sao_informadas():
    result = AriStagingValidator().validate(
        base_url='https://staging.example.com/analytics-runtime-intelligence',
        screenshot_captured=True,
        smoke_deploy_ok=True,
    )

    assert result['staging_ready'] is True
    assert result['blockers'] == []
