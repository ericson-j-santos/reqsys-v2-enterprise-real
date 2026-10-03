from __future__ import annotations

from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient

from app.api import report_builder_delivery as api_module
from app.api.report_builder_delivery import require_report_builder_send_auth
from app.main import app
from app.schemas.report_builder_delivery import ReportBuilderEmailRequest
from app.services import report_builder_delivery as service
from app.services.movimento_email.sender_factory import ConfiguracaoEnvioError
from app.services.movimento_email.smtp_sender import EnvioEmailError


def _payload(*, dry_run: bool = True, recipients: list[str] | None = None) -> ReportBuilderEmailRequest:
    return ReportBuilderEmailRequest(
        report={
            'report_name': 'ReportBuilderSmoke',
            'display_name': 'Report Builder - Prova E2E',
            'description': 'Relatório de prova do fluxo gerar e enviar.',
            'target_environment': 'dev',
            'query': (
                "SELECT 'Report Builder' AS Componente, 'Gerado pela aplicacao' AS Status "
                "UNION ALL SELECT 'Entrega', 'Email governado' AS Status"
            ),
            'fields': [
                {'name': 'Componente', 'title': 'Componente', 'data_type': 'String'},
                {'name': 'Status', 'title': 'Status', 'data_type': 'String'},
            ],
            'dry_run': True,
        },
        recipients=recipients or ['ericson.takay@gmail.com'],
        dry_run=dry_run,
    )


class _FakeSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def enviar(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest.fixture
def auth_override():
    app.dependency_overrides[require_report_builder_send_auth] = lambda: object()
    yield
    app.dependency_overrides.pop(require_report_builder_send_auth, None)


def test_dry_run_gera_relatorio_sem_chamar_provedor_externo(monkeypatch):
    monkeypatch.setattr(service, 'resolver_provedor_envio', lambda: 'graph')
    monkeypatch.setattr(
        service,
        'resolver_remetente_configurado',
        lambda _settings, permitir_placeholder=False: 'dry-run@example.invalid',
    )

    def _nao_deve_criar_sender(_settings):
        raise AssertionError('sender externo não pode ser criado em dry_run')

    monkeypatch.setattr(service, 'criar_sender_email_movimento', _nao_deve_criar_sender)

    result = service.gerar_e_enviar_relatorio(_payload(dry_run=True))

    assert result['status'] == 'planned'
    assert result['delivery']['external_write_performed'] is False
    assert result['delivery']['recipients'] == ['ericson.takay@gmail.com']
    assert result['report']['attachment_name'] == 'ReportBuilderSmoke.rdl'
    assert len(result['report']['definition_sha256']) == 64


def test_envio_real_anexa_rdl_e_correlation_id(monkeypatch):
    fake_sender = _FakeSender()
    monkeypatch.setattr(service, 'resolver_provedor_envio', lambda: 'graph')
    monkeypatch.setattr(
        service,
        'criar_sender_email_movimento',
        lambda _settings: (fake_sender, 'reports@example.com', 'graph'),
    )

    result = service.gerar_e_enviar_relatorio(_payload(dry_run=False))

    assert result['status'] == 'sent'
    assert result['delivery']['external_write_performed'] is True
    assert len(fake_sender.messages) == 1

    message = fake_sender.messages[0]
    assert message['To'] == 'ericson.takay@gmail.com'
    assert message['X-Correlation-ID'] == result['correlation_id']
    assert message['X-Report-SHA256'] == result['report']['definition_sha256']

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == 'ReportBuilderSmoke.rdl'
    assert attachments[0].get_content().startswith(b'<?xml')


def test_endpoint_dry_run_exercita_fluxo_da_aplicacao(monkeypatch, auth_override):
    monkeypatch.setattr(service, 'resolver_provedor_envio', lambda: 'graph')
    monkeypatch.setattr(
        service,
        'resolver_remetente_configurado',
        lambda _settings, permitir_placeholder=False: 'dry-run@example.invalid',
    )

    client = TestClient(app)
    response = client.post(
        '/v1/report-builder/reports/generate-and-email',
        json=_payload(dry_run=True).model_dump(mode='json'),
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'planned'
    assert data['report']['attachment_name'] == 'ReportBuilderSmoke.rdl'
    assert data['delivery']['external_write_performed'] is False


def test_endpoint_rejeita_destinatario_invalido(auth_override):
    client = TestClient(app)
    payload = _payload(dry_run=True).model_dump(mode='json')
    payload['recipients'] = ['nao-e-email']

    response = client.post('/v1/report-builder/reports/generate-and-email', json=payload)

    assert response.status_code == 422


def test_endpoint_rejeita_sql_destrutivo(auth_override):
    client = TestClient(app)
    payload = _payload(dry_run=True).model_dump(mode='json')
    payload['report']['query'] = 'DELETE FROM tbDemandas'

    response = client.post('/v1/report-builder/reports/generate-and-email', json=payload)

    assert response.status_code == 422


def test_endpoint_mascara_detalhe_de_configuracao(monkeypatch, auth_override):
    def _falhar(_payload):
        raise ConfiguracaoEnvioError('AZURE_CLIENT_SECRET=nao-expor')

    monkeypatch.setattr(api_module, 'gerar_e_enviar_relatorio', _falhar)
    client = TestClient(app)
    response = client.post(
        '/v1/report-builder/reports/generate-and-email',
        json=_payload(dry_run=False).model_dump(mode='json'),
    )

    assert response.status_code == 409
    assert response.json()['detail'] == 'Configuração de envio de e-mail indisponível.'
    assert 'nao-expor' not in response.text


def test_endpoint_mascara_detalhe_de_falha_do_provedor(monkeypatch, auth_override):
    def _falhar(_payload):
        raise EnvioEmailError('password=nao-expor')

    monkeypatch.setattr(api_module, 'gerar_e_enviar_relatorio', _falhar)
    client = TestClient(app)
    response = client.post(
        '/v1/report-builder/reports/generate-and-email',
        json=_payload(dry_run=False).model_dump(mode='json'),
    )

    assert response.status_code == 502
    assert response.json()['detail'] == 'Falha ao enviar relatório por e-mail.'
    assert 'nao-expor' not in response.text
