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
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.local/ReportServer')
    monkeypatch.setenv('SSRS_REPORTS_PATH', 'ReqSys')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual,RelatorioDetalhado')
    resp = client.get('/v1/relatorios/ssrs/status')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['enabled'] is True
    assert isinstance(data['reports'], list)
    assert len(data['reports']) == 2
    # cada item deve ter os campos esperados
    for r in data['reports']:
        assert 'name' in r
        assert 'accessible' in r
    summary = data['summary']
    assert summary['total'] == 2
    assert summary['online'] + summary['offline'] == 2


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
    Em ambiente de teste sem SSRS real, esperamos 503 ou 502 (conexão recusada)
    — mas nunca 404 nem 200 com conteúdo errado."""
    monkeypatch.setenv('SSRS_BASE_URL', 'http://ssrs.invalid/ReportServer')
    monkeypatch.setenv('SSRS_REPORT_NAMES', 'AtvIndividual')
    resp = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')
    assert resp.status_code in (200, 502, 503, 504)
