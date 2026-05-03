def test_ssrs_links_desabilitado_sem_base(client, monkeypatch):
    monkeypatch.delenv('SSRS_BASE_URL', raising=False)
    resp = client.get('/v1/relatorios/ssrs')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is False
    assert data['reports'] == []


def test_ssrs_links_com_base(client, monkeypatch):
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.local/ReportServer')
    monkeypatch.setenv('SSRS_REPORTS_PATH', 'ReqSys')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual,RelatorioDetalhado')

    resp = client.get('/v1/relatorios/ssrs')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is True
    assert len(data['reports']) == 2
    assert data['reports'][0]['name'] == 'AtvIndividual'
    assert 'rs:Command=Render' in data['reports'][0]['render_url']


def test_ssrs_health_desabilitado_sem_base(client, monkeypatch):
    monkeypatch.delenv('SSRS_BASE_URL', raising=False)
    resp = client.get('/v1/relatorios/ssrs/health')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is False
    assert data['reachable'] is False
