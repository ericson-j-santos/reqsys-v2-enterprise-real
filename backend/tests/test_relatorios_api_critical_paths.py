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
def test_ssrs_pdf_download_proxy(mock_get, client, monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_BASE_URL': 'https://ssrs.example.com/ReportServer',
        'SSRS_REPORTS_PATH': 'ReqSys',
    }.get(key, default))
    monkeypatch.setattr(rel, '_get_ssrs_auth', lambda: None)
    mock_get.return_value = MagicMock(
        status_code=200,
        headers={'Content-Type': 'application/pdf'},
        content=b'%PDF-1.4',
        raise_for_status=lambda: None,
    )

    response = client.get('/v1/relatorios/ssrs/AtvIndividual/pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
