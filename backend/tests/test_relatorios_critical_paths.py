"""Testes de caminhos críticos — helpers SSRS em relatorios.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api import relatorios as rel


def test_list_reports_usa_default_quando_env_vazio(monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': '' if key == 'SSRS_REPORT_NAMES' else default)

    reports = rel._list_reports()

    assert 'AtvIndividual' in reports
    assert len(reports) >= 3


def test_list_reports_parseia_csv(monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': 'RelA, RelB' if key == 'SSRS_REPORT_NAMES' else default)

    assert rel._list_reports() == ['RelA', 'RelB']


def test_ssrs_flags_https_e_tls(monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_REQUIRE_HTTPS': 'true',
        'SSRS_VERIFY_TLS': 'false',
    }.get(key, default))

    assert rel._ssrs_require_https() is True
    assert rel._ssrs_verify_tls() is False


def test_normalize_ssrs_base_url_forca_https():
    assert rel._normalize_ssrs_base_url('http://ssrs.local/ReportServer', True).startswith('https://')


def test_build_ssrs_urls_incluem_pasta_e_relatorio():
    render = rel._build_ssrs_render_url('https://ssrs.local', 'ReqSys', 'AtvIndividual')
    pdf = rel._build_ssrs_pdf_url('https://ssrs.local', 'ReqSys', 'AtvIndividual')

    assert 'rs:Command=Render' in render
    assert 'rs:Format=PDF' in pdf
    assert 'ReqSys' in render


def test_get_ssrs_auth_ntlm_quando_credenciais_presentes(monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': {
        'SSRS_USER': 'DOMAIN\\user',
        'SSRS_PASSWORD': 'secret',
    }.get(key, default))

    auth = rel._get_ssrs_auth()

    assert auth is not None
    assert auth.username == 'DOMAIN\\user'


def test_get_ssrs_auth_sem_sspi_levanta_http_exception(monkeypatch):
    monkeypatch.setattr(rel, 'get_secret', lambda key, default='': default)
    monkeypatch.setattr(rel, '_SSPI_AVAILABLE', False)

    with pytest.raises(HTTPException) as exc:
        rel._get_ssrs_auth()

    assert exc.value.status_code == 503


@patch('app.api.relatorios._requests.head')
@patch('app.api.relatorios._requests.get')
def test_check_report_accessibility_faz_fallback_para_get(mock_get, mock_head, monkeypatch):
    monkeypatch.setattr(rel, '_ssrs_verify_tls', lambda: True)
    mock_head.return_value = MagicMock(status_code=405)
    mock_get.return_value = MagicMock(status_code=200)

    status = rel._check_report_accessibility('https://ssrs.local/render', auth=None)

    assert status == 200
    mock_get.assert_called_once()
