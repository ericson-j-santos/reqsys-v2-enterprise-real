from fastapi.testclient import TestClient

from app.core.autonomous_operations import (
    calcular_score_consolidado,
    classificar_nivel,
    classificar_risco,
    criar_acoes_base,
    criar_indicadores_base,
    criar_politicas_base,
    gerar_snapshot_operacao_autonoma,
)
from app.core.runtime_remediation import (
    RemediationRequest,
    avaliar_remediacao,
    criar_health_snapshot_base,
)
from app.core.security import criar_token
from app.main import app


def _admin_headers(correlation_id: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {criar_token({"sub": "test-admin", "papel": "admin"})}'}
    if correlation_id:
        headers['X-Correlation-ID'] = correlation_id
    return headers


def test_operacao_autonoma_maturidade_status_200():
    res = TestClient(app).get('/operacao-autonoma/maturidade')

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['schema_version'] == '1.0.0'
    assert body['data']['resumo']['score_consolidado'] < body['data']['resumo']['score_alvo']
    assert body['data']['resumo']['seguranca_consolidada'] is False
    assert body['data']['resumo']['pronto_para_auto_remediacao_total'] is False


def test_operacao_autonoma_propaga_correlation_id():
    correlation_id = 'corr-aop-p0-1-test'
    res = TestClient(app).get('/operacao-autonoma/maturidade', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_operacao_autonoma_mantem_estado_evidenciado_sem_inflar_maturidade():
    snapshot = gerar_snapshot_operacao_autonoma('corr-evidencia')

    assert snapshot.resumo.estado_atual_evidenciado != 'avancado'
    assert snapshot.resumo.gap_consolidado > 0
    assert any('Estado atual não deve ser elevado sem evidência' in decisao for decisao in snapshot.decisoes_governanca)


def test_operacao_autonoma_expoe_pilares_prioritarios():
    res = TestClient(app).get('/operacao-autonoma/maturidade')
    pilares = {indicador['pilar'] for indicador in res.json()['data']['indicadores']}

    assert {'Operação Autônoma', 'Observabilidade', 'Segurança Enterprise', 'CI/CD Governado', 'Governança', 'Runtime Intelligence'} <= pilares


def test_operacao_autonoma_politicas_bloqueiam_acao_destrutiva_sem_health_validator():
    res = TestClient(app).get('/operacao-autonoma/maturidade')
    acoes = {acao['codigo']: acao for acao in res.json()['data']['acoes_autonomas']}

    assert acoes['AOP-ACT-003']['estado'] == 'bloqueado_por_politica'
    assert 'health validator por componente' in acoes['AOP-ACT-003']['validacoes_obrigatorias']


def test_calcular_score_consolidado_base_controlado():
    indicadores = criar_indicadores_base()
    score = calcular_score_consolidado(indicadores)

    assert 0 < score < 95


def test_calcular_score_consolidado_sem_indicadores_retorna_zero():
    assert calcular_score_consolidado([]) == 0


def test_classificar_nivel_por_faixas():
    assert classificar_nivel(95) == 'avancado'
    assert classificar_nivel(80) == 'intermediario_avancado'
    assert classificar_nivel(55) == 'intermediario'
    assert classificar_nivel(10) == 'inicial'


def test_classificar_risco_por_score_e_gap_critico():
    assert classificar_risco(90, 0) == 'baixa'
    assert classificar_risco(80, 0) == 'media'
    assert classificar_risco(60, 0) == 'alta'
    assert classificar_risco(95, 1) == 'critica'
    assert classificar_risco(40, 0) == 'critica'


def test_politicas_base_expoem_bloqueios_e_limites():
    politicas = {politica.codigo: politica for politica in criar_politicas_base()}

    assert politicas['AOP-CI-RETRY-001'].habilitada is True
    assert politicas['AOP-CI-RETRY-001'].limite_execucoes == 2
    assert politicas['AOP-RUN-HEALTH-001'].habilitada is False
    assert 'desabilitada até existir health validator por componente' in politicas['AOP-RUN-HEALTH-001'].bloqueios


def test_acoes_base_preservam_bloqueio_para_restart():
    acoes = {acao.codigo: acao for acao in criar_acoes_base()}

    assert acoes['AOP-ACT-001'].estado == 'apto_auto_remediacao'
    assert acoes['AOP-ACT-002'].severidade == 'critica'
    assert acoes['AOP-ACT-003'].estado == 'bloqueado_por_politica'


def test_runtime_health_validator_expoe_componentes_e_bloqueios():
    res = TestClient(app).get('/operacao-autonoma/runtime-health')

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['score_global'] < 100
    assert 'execucao_real_bloqueada_no_p0_2' in body['data']['bloqueios_operacionais']
    assert 'restart_real_bloqueado_sem_auditoria_persistente' in body['data']['bloqueios_operacionais']
    componentes = {componente['componente'] for componente in body['data']['componentes']}
    assert {'api_fastapi', 'observabilidade', 'auto_remediacao_runtime', 'persistencia_auditoria'} <= componentes


def test_runtime_health_validator_propaga_correlation_id():
    correlation_id = 'corr-runtime-health-test'
    res = TestClient(app).get('/operacao-autonoma/runtime-health', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_runtime_health_validator_aceita_x_request_id_como_fallback():
    request_id = 'req-runtime-health-test'
    res = TestClient(app).get('/operacao-autonoma/runtime-health', headers={'X-Request-ID': request_id})

    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == request_id
    assert body['data']['correlation_id'] == request_id


def test_executor_governado_exige_admin():
    payload = {
        'codigo_acao': 'AOP-ACT-004',
        'componente': 'auto_remediacao_runtime',
        'tipo': 'retry_governado',
        'motivo': 'falha transitÃ³ria simulada',
        'dry_run': True,
    }
    res = TestClient(app).post('/operacao-autonoma/remediacoes/avaliar', json=payload)

    assert res.status_code == 401


def test_executor_governado_permite_retry_nao_destrutivo_em_dry_run():
    payload = {
        'codigo_acao': 'AOP-ACT-004',
        'componente': 'auto_remediacao_runtime',
        'tipo': 'retry_governado',
        'motivo': 'falha transitória simulada',
        'dry_run': True,
    }
    res = TestClient(app).post('/operacao-autonoma/remediacoes/avaliar', json=payload, headers=_admin_headers())

    assert res.status_code == 200
    data = res.json()['data']
    assert data['permitido'] is True
    assert data['estado'] == 'permitido_dry_run'
    assert data['dry_run'] is True
    assert data['politica_aplicada'] == 'AOP-RUN-RETRY-001'
    assert 'reexecutar_acao_transitoria_com_limite' in data['comandos_planejados']


def test_executor_governado_bloqueia_execucao_real_nao_destrutiva_no_p0_2():
    payload = {
        'codigo_acao': 'AOP-ACT-005',
        'componente': 'auto_remediacao_runtime',
        'tipo': 'registrar_incidente',
        'motivo': 'incidente simulado',
        'dry_run': False,
    }
    res = TestClient(app).post('/operacao-autonoma/remediacoes/avaliar', json=payload, headers=_admin_headers())

    assert res.status_code == 200
    data = res.json()['data']
    assert data['permitido'] is False
    assert data['estado'] == 'bloqueado_por_politica'
    assert data['dry_run'] is False
    assert data['politica_aplicada'] == 'AOP-RUN-DRY-RUN-BYPASS-DENY-001'
    assert 'execucao real nao e permitida no P0.2; envie dry_run=true' in data['razoes']


def test_executor_governado_permite_bloquear_deploy_em_dry_run():
    health = criar_health_snapshot_base('corr-health', 'testes')
    request = RemediationRequest(
        codigo_acao='AOP-ACT-002',
        componente='api_fastapi',
        tipo='bloquear_deploy',
        motivo='gate de segurança simulado',
    )

    decisao = avaliar_remediacao(request, health, 'corr-health')

    assert decisao.permitido is True
    assert decisao.estado == 'permitido_dry_run'
    assert decisao.politica_aplicada == 'AOP-RUN-GOVERNED-NON-DESTRUCTIVE-001'
    assert decisao.comandos_planejados == ['bloquear_deploy']


def test_executor_governado_permite_observacao_em_dry_run():
    health = criar_health_snapshot_base('corr-health', 'testes')
    request = RemediationRequest(
        codigo_acao='AOP-ACT-006',
        componente='observabilidade',
        tipo='observacao',
        motivo='observação operacional simulada',
    )

    decisao = avaliar_remediacao(request, health, 'corr-health')

    assert decisao.permitido is True
    assert decisao.estado == 'permitido_dry_run'
    assert decisao.comandos_planejados == ['observacao']


def test_executor_governado_bloqueia_restart_real_por_politica():
    payload = {
        'codigo_acao': 'AOP-ACT-003',
        'componente': 'auto_remediacao_runtime',
        'tipo': 'restart_controlado',
        'motivo': 'health degradado simulado',
        'dry_run': False,
    }
    res = TestClient(app).post('/operacao-autonoma/remediacoes/avaliar', json=payload, headers=_admin_headers())

    assert res.status_code == 200
    data = res.json()['data']
    assert data['permitido'] is False
    assert data['dry_run'] is False
    assert data['estado'] == 'bloqueado_por_politica'
    assert data['politica_aplicada'] == 'AOP-RUN-DRY-RUN-BYPASS-DENY-001'
    assert 'execucao real nao e permitida no P0.2; envie dry_run=true' in data['razoes']


def test_executor_governado_bloqueia_rollback_real_por_politica():
    health = criar_health_snapshot_base('corr-health', 'testes')
    request = RemediationRequest(
        codigo_acao='AOP-ACT-007',
        componente='auto_remediacao_runtime',
        tipo='rollback_seguro',
        motivo='rollback simulado',
        dry_run=False,
    )

    decisao = avaliar_remediacao(request, health, 'corr-health')

    assert decisao.permitido is False
    assert decisao.estado == 'bloqueado_por_politica'
    assert decisao.dry_run is False
    assert decisao.politica_aplicada == 'AOP-RUN-DRY-RUN-BYPASS-DENY-001'
    assert 'execucao real nao e permitida no P0.2; envie dry_run=true' in decisao.razoes


def test_executor_governado_bloqueia_componente_desconhecido():
    health = criar_health_snapshot_base('corr-health', 'testes')
    request = RemediationRequest(
        codigo_acao='AOP-ACT-999',
        componente='componente_inexistente',
        tipo='retry_governado',
        motivo='teste componente inexistente',
    )

    decisao = avaliar_remediacao(request, health, 'corr-health')

    assert decisao.permitido is False
    assert decisao.estado == 'bloqueado_por_politica'
    assert decisao.politica_aplicada == 'AOP-RUN-UNKNOWN-COMPONENT-001'


def test_classificar_estado_por_score_bandas():
    from app.core.runtime_remediation import _classificar_estado_por_score

    assert _classificar_estado_por_score(90) == 'saudavel'
    assert _classificar_estado_por_score(70) == 'degradado'
    assert _classificar_estado_por_score(40) == 'critico'
    assert _classificar_estado_por_score(0) == 'desconhecido'


def test_avaliar_remediacao_bloqueia_restart_em_dry_run():
    health = criar_health_snapshot_base('corr-health', 'testes')
    request = RemediationRequest(
        codigo_acao='AOP-ACT-003',
        componente='auto_remediacao_runtime',
        tipo='restart_controlado',
        motivo='restart simulado',
        dry_run=True,
    )

    decisao = avaliar_remediacao(request, health, 'corr-health')

    assert decisao.permitido is False
    assert decisao.politica_aplicada == 'AOP-RUN-DESTRUCTIVE-BLOCK-001'
