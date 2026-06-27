from app.services.reqsys_orchestrator import OrchestratorDemand, classificar_demanda, listar_coordenadores


def test_classificador_direciona_ci_para_coordenador_cicd():
    rota = classificar_demanda(OrchestratorDemand(
        titulo='CI falhou no PR runtime',
        descricao='Backend Tests + Coverage falhou no GitHub Actions e precisa de rerun com evidencia.',
        origem='chat',
        ambiente='dev',
    ))

    assert rota['tema'] == 'ci_cd'
    assert rota['coordinator']['id'] == 'reqsys-ci-coordinator'
    assert rota['pipeline_sugerido'] == 'ci-router-result'
    assert 'ci' in rota['labels']
    assert 'ambiente:dev' in rota['labels']
    assert rota['governanca']['requer_aprovacao_humana'] is True
    assert rota['governanca']['permite_acao_destrutiva'] is False


def test_classificador_direciona_govbi_para_coordenador_analytics():
    rota = classificar_demanda(OrchestratorDemand(
        titulo='Criar dashboard GovBI com indicadores executivos',
        descricao='Power BI, KPIs, SQL e analytics operacional com drill-down.',
    ))

    assert rota['tema'] == 'govbi'
    assert rota['coordinator']['id'] == 'reqsys-govbi-coordinator'
    assert 'govbi' in rota['labels']
    assert rota['confianca'] >= 0.7


def test_orchestrator_expoe_catalogo_de_coordenadores():
    coordenadores = listar_coordenadores()
    ids = {coordenador['coordinator_id'] for coordenador in coordenadores}

    assert 'reqsys-runtime-coordinator' in ids
    assert 'reqsys-agile-coordinator' in ids
    assert 'reqsys-ai-coordinator' in ids
    assert 'reqsys-security-coordinator' in ids


def test_endpoint_orchestrator_route(client, correlation_id):
    resp = client.post(
        '/v1/agents/orchestrator/route',
        json={
            'titulo': 'Sincronizar ambientes Fly.io',
            'descricao': 'Validar deploy, health, readiness e drift entre dev, homologacao e producao.',
            'origem': 'chat-fixado',
            'ambiente': 'hml',
        },
        headers={'X-Correlation-ID': correlation_id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == correlation_id
    data = body['data']
    assert data['tema'] == 'runtime'
    assert data['coordinator']['id'] == 'reqsys-runtime-coordinator'
    assert data['governanca']['modo_execucao'] == 'assistido'
    assert 'ambiente:hml' in data['labels']


def test_endpoint_orchestrator_batch(client):
    resp = client.post('/v1/agents/orchestrator/route/batch', json={
        'demandas': [
            {'titulo': 'Nova sprint Scrum', 'descricao': 'Planejar backlog agile'},
            {'titulo': 'Revisar JWT e RBAC', 'descricao': 'Seguranca, token e auditoria'},
        ]
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['total'] == 2
    assert data['por_tema']['agile_scrum'] == 1
    assert data['por_tema']['seguranca_governanca'] == 1


def test_endpoint_orchestrator_persiste_evento_e_expõe_analytics(client, correlation_id):
    resp = client.post(
        '/v1/agents/orchestrator/route',
        json={
            'titulo': 'Pipeline CI com falha critica',
            'descricao': 'Workflow GitHub Actions com pytest, coverage e gate de merge bloqueado.',
            'origem': 'pytest-analytics',
            'prioridade_informada': 'alta',
            'ambiente': 'dev',
        },
        headers={'X-Correlation-ID': correlation_id},
    )

    assert resp.status_code == 200
    rota = resp.json()['data']
    assert rota['routing_event_id'] > 0
    assert rota['correlation_id'] == correlation_id

    summary = client.get('/v1/agents/orchestrator/analytics/summary')
    assert summary.status_code == 200
    summary_data = summary.json()['data']
    assert summary_data['total_eventos'] >= 1
    assert summary_data['confianca_media'] > 0

    themes = client.get('/v1/agents/orchestrator/analytics/themes')
    assert themes.status_code == 200
    assert any(item['valor'] == 'ci_cd' for item in themes.json()['data']['themes'])

    coordinators = client.get('/v1/agents/orchestrator/analytics/coordinators')
    assert coordinators.status_code == 200
    assert any(item['valor'] == 'reqsys-ci-coordinator' for item in coordinators.json()['data']['coordinators'])

    risk = client.get('/v1/agents/orchestrator/analytics/risk')
    assert risk.status_code == 200
    assert risk.json()['data']['risk']['prioridade_alta'] >= 1
