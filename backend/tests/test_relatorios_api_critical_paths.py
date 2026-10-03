"""Testes de caminhos críticos — rotas API de relatórios SSRS."""

from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api import relatorios as rel


@patch('app.api.relatorios._requests.get')
def test_ssrs_health_sem_base_url(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': '')

    response = client.get('/v1/relatorios/ssrs/health')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['enabled'] is False
    mock_get.assert_not_called()


@patch('app.api.relatorios._requests.get')
def test_ssrs_health_reachable(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REQUIRE_HTTPS': 'true',
        'SSRS_VERIFY_TLS': 'true',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(status_code=200)

    response = client.get('/v1/relatorios/ssrs/health')

    assert response.status_code == 200
    assert response.json()['data']['reachable'] is True


@patch('app.api.relatorios._check_report_accessibility', return_value=200)
@patch('app.api.relatorios._get_ssrs_auth')
def test_ssrs_status_lista_relatorios(mock_auth, mock_check, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORTS_PATH': 'ReqSys',
        'SSRS_REPORT_NAMES': 'RelA,RelB',
    }.get(key, default))
    mock_auth.return_value = MagicMock()

    response = client.get('/v1/relatorios/ssrs/status')

    assert response.status_code == 200
    body = response.json()['data']
    assert body['enabled'] is True
    assert body['summary']['total'] == 2
    assert body['summary']['online'] == 2


@patch('app.api.relatorios._get_ssrs_auth', side_effect=HTTPException(status_code=503, detail='auth indisponivel'))
def test_ssrs_status_marca_offline_sem_auth(_auth, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORT_NAMES': 'RelA',
    }.get(key, default))

    response = client.get('/v1/relatorios/ssrs/status')

    assert response.status_code == 200
    reports = response.json()['data']['reports']
    assert reports[0]['accessible'] is False
    assert reports[0]['detail'] == 'auth indisponivel'


@patch('app.api.relatorios._requests.get')
def test_ssrs_links_desabilitado_sem_base_url(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': '')

    response = client.get('/v1/relatorios/ssrs')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['enabled'] is False
    assert data['reports'] == []
    mock_get.assert_not_called()


@patch('app.api.relatorios._requests.get')
def test_ssrs_health_request_exception(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_USER': 'user',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.side_effect = rel._requests.exceptions.Timeout('timeout')

    response = client.get('/v1/relatorios/ssrs/health')

    assert response.status_code == 200
    body = response.json()['data']
    assert body['reachable'] is False
    assert 'timeout' in body['detail']


def test_check_report_accessibility_unitario_faz_fallback_get():
    mock_head = MagicMock(status_code=405)
    mock_get_resp = MagicMock(status_code=200)
    with patch('app.api.relatorios._requests.head', return_value=mock_head):
        with patch('app.api.relatorios._requests.get', return_value=mock_get_resp) as mock_get_fn:
            status = rel._check_report_accessibility('https://ssrs.example/render', None)
    assert status == 200
    mock_get_fn.assert_called_once()
    mock_get_resp.close.assert_called_once()


@patch('app.api.relatorios._requests.head', return_value=MagicMock(status_code=405))
@patch('app.api.relatorios._requests.get')
def test_check_report_accessibility_faz_fallback_get_quando_head_405(mock_get, _head, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORTS_PATH': 'ReqSys',
        'SSRS_REPORT_NAMES': 'RelA',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(status_code=200, close=MagicMock())

    response = client.get('/v1/relatorios/ssrs/status')

    assert response.status_code == 200
    assert response.json()['data']['reports'][0]['accessible'] is True
    mock_get.assert_called_once()


@patch('app.api.relatorios._check_report_accessibility', side_effect=rel._requests.exceptions.Timeout('timeout'))
@patch('app.api.relatorios._get_ssrs_auth')
def test_ssrs_status_marca_offline_em_request_exception(_auth, _check, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORT_NAMES': 'RelA',
    }.get(key, default))
    _auth.return_value = MagicMock()

    response = client.get('/v1/relatorios/ssrs/status')

    assert response.status_code == 200
    report = response.json()['data']['reports'][0]
    assert report['accessible'] is False
    assert 'timeout' in report['detail']


@patch('app.api.relatorios._requests.get')
def test_ssrs_links_habilitado_lista_relatorios(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORTS_PATH': 'ReqSys',
        'SSRS_REPORT_NAMES': 'RelA',
    }.get(key, default))

    response = client.get('/v1/relatorios/ssrs')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['enabled'] is True
    assert data['reports'][0]['name'] == 'RelA'
    assert 'render_url' in data['reports'][0]
    mock_get.assert_not_called()


@patch('app.api.relatorios._requests.head', return_value=MagicMock(status_code=200))
def test_check_report_accessibility_retorna_status_head(_head):
    status = rel._check_report_accessibility('https://ssrs.example/render', None)
    assert status == 200


def test_get_ssrs_auth_negotiate_quando_sspi_disponivel(monkeypatch):
    negotiate = MagicMock()
    monkeypatch.setattr(rel, '_SSPI_AVAILABLE', True)
    monkeypatch.setattr(rel, '_HttpNegotiateAuth', negotiate)
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': '')

    auth = rel._get_ssrs_auth()

    negotiate.assert_called_once()
    assert auth is negotiate.return_value


@patch('app.api.relatorios._requests.get')
def test_ssrs_pdf_download_proxy(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORTS_PATH': 'ReqSys',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(
        status_code=200,
        headers={'Content-Type': 'application/pdf'},
        iter_content=lambda chunk_size=8192: [b'%PDF-1.4', b'chunk2'],
        raise_for_status=lambda: None,
    )

    response = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
    assert response.content == b'%PDF-1.4chunk2'


@patch('app.api.relatorios._requests.get')
def test_ssrs_pdf_401_retorna_502(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(status_code=401)

    response = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')

    assert response.status_code == 502
    assert '401' in response.json()['detail']


@patch('app.api.relatorios._requests.get')
def test_ssrs_pdf_status_4xx_propaga(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(status_code=404)

    response = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')

    assert response.status_code == 404


@patch('app.api.relatorios._requests.get')
def test_ssrs_pdf_request_exception_retorna_502(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.side_effect = rel._requests.exceptions.ConnectionError('offline')

    response = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')

    assert response.status_code == 502
    assert 'offline' in response.json()['detail']
