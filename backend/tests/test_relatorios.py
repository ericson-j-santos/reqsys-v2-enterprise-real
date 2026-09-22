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


# ─── /ssrs/status ─────────────────────────────────────────────────────────────

def test_ssrs_status_desabilitado_sem_base(client, monkeypatch):
    monkeypatch.delenv('SSRS_BASE_URL', raising=False)
    resp = client.get('/v1/relatorios/ssrs/status')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is False
    assert data['reports'] == []
    assert 'checked_at' in data
    summary = data.get('summary', {})
    assert summary.get('total', 0) == 0


def test_ssrs_status_com_base_retorna_lista(client, monkeypatch):
    """Testa /ssrs/status com base configurada.
    Em ambiente sem SSPI (Linux CI), retorna 200 com relatórios marcados como offline."""
    monkeypatch.delenv('SSRS_USER', raising=False)
    monkeypatch.delenv('SSRS_PASSWORD', raising=False)
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.local/ReportServer')
    monkeypatch.setenv('SSRS_REPORTS_PATH', 'ReqSys')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual,RelatorioDetalhado')
    resp = client.get('/v1/relatorios/ssrs/status')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is True
    assert isinstance(data['reports'], list)
    assert len(data['reports']) == 2
    # Em ambiente sem SSPI/credenciais, todos os relatórios marcados como offline
    for r in data['reports']:
        assert 'name' in r
        assert 'accessible' in r
        # Sem autenticação, todos devem estar inacessíveis
        assert r['accessible'] is False
    summary = data['summary']
    assert summary['total'] == 2
    assert summary['online'] == 0
    assert summary['offline'] == 2


# ─── /ssrs/{nome}/pdf ─────────────────────────────────────────────────────────

def test_ssrs_pdf_sem_base_retorna_503(client, monkeypatch):
    monkeypatch.delenv('SSRS_BASE_URL', raising=False)
    resp = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')
    assert resp.status_code == 503


def test_ssrs_pdf_nome_invalido_retorna_404(client, monkeypatch):
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.local/ReportServer')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual,RelatorioDetalhado')
    resp = client.get('/v1/relatorios/ssrs/RelatorioInexistente/pdf')
    assert resp.status_code == 404


def test_ssrs_pdf_nome_valido_tenta_proxy(client, monkeypatch):
    """Com base configurada e nome válido, o backend tenta acessar o SSRS.
    Em ambiente de teste sem credenciais SSRS configuradas, esperamos 503.
    Quando não há SSPI disponível e SSRS_USER/SSRS_PASSWORD não estão configurados."""
    monkeypatch.delenv('SSRS_USER', raising=False)
    monkeypatch.delenv('SSRS_PASSWORD', raising=False)
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.invalid/ReportServer')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual')
    resp = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')
    # Sem credenciais e sem SSPI disponível no ambiente Linux, deve retornar 503
    assert resp.status_code == 503
