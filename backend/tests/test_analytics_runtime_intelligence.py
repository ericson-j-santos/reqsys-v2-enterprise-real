from app.api.analytics_runtime_intelligence import _calcular_health_score, _snapshot_ari, _validacoes_base
from app.services.ari_runtime_sql_adapter import AriRuntimeSqlAdapter
from app.services.ari_staging_validator import AriStagingValidator


def test_analytics_runtime_intelligence_snapshot_falha_fechado_sem_evidencia_externa(client):
    resp = client.get(
        '/api/analytics-runtime-intelligence/snapshot',
        headers={'X-Correlation-ID': 'corr-ari-test'},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True

    data = payload['data']
    assert data['capability'] == 'Analytics Runtime Intelligence'
    assert data['correlation_id'] == 'corr-ari-test'
    assert data['evidence_scope'] == 'repository_contract'
    assert 0 <= data['health_score'] <= 100
    assert data['production_ready'] is False
    assert data['draft_recomendado'] is True
    assert data['runtime_sql_validation']['production_evidence'] is False
    assert data['staging_validation']['staging_ready'] is False
    assert data['telemetry_validation']['telemetry_ready'] is False
    assert data['lineage_validation']['lineage_ready'] is False
    assert any(item['bloqueia_producao'] for item in data['readiness_matrix'])


def test_alias_v1_preserva_contrato(client):
    resp = client.get('/v1/analytics-runtime-intelligence/snapshot')
    assert resp.status_code == 200
    assert resp.json()['data']['production_ready'] is False


def test_ari_validacoes_base_contem_scores_e_status_operacionais():
    validacoes = _validacoes_base()

    assert len(validacoes) == 10
    assert all(0 <= item['score'] <= 100 for item in validacoes)
    assert {item['status'] for item in validacoes}.issubset({'ok', 'warn', 'fail', 'block'})
    assert 0 <= _calcular_health_score(validacoes) <= 100


def test_ari_snapshot_nao_promove_figma_sem_evidencia():
    snapshot = _snapshot_ari('corr-figma')

    assert snapshot['figma']['status'] == 'evidence_pending'
    assert snapshot['figma']['ready'] is False
    assert snapshot['production_ready'] is False


def test_runtime_sql_adapter_valida_consulta_estatica_sem_promover_evidencia():
    sql = 'select count(*) total, status from requisitos where status is not null group by status'
    result = AriRuntimeSqlAdapter().validate(sql, null_critical=0)

    assert result['runtime_sql_ready'] is True
    assert result['execution_mode'] == 'static_only'
    assert result['production_evidence'] is False
    assert result['query_sha256']
    assert not result['blockers']


def test_runtime_sql_adapter_bloqueia_comando_destrutivo():
    result = AriRuntimeSqlAdapter().validate('delete from requisitos where id = 1')

    assert result['runtime_sql_ready'] is False
    assert any(item['regra'] == 'DESTRUCTIVE_SQL' for item in result['blockers'])


def test_runtime_sql_adapter_bloqueia_null_critico():
    result = AriRuntimeSqlAdapter().validate('select * from requisitos', null_critical=2)

    assert result['runtime_sql_ready'] is False
    assert any(item['regra'] == 'NULL_CRITICAL' for item in result['blockers'])


def test_staging_validator_default_falha_fechado():
    result = AriStagingValidator().validate()

    assert result['staging_ready'] is False
    assert len(result['blockers']) == 3


def test_staging_validator_aprova_apenas_evidencia_explicitamente_fornecida():
    result = AriStagingValidator().validate(
        base_url='https://staging.example.com',
        screenshot_captured=True,
        smoke_deploy_ok=True,
        evidence_artifact='artifact://ari/staging/readback',
    )

    assert result['staging_ready'] is True
    assert result['blockers'] == []
