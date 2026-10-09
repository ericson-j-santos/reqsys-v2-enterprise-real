from types import SimpleNamespace

from app.services.movimento_email import sender_factory
from app.services.movimento_email.graph_sender import GraphEmailSender


def _settings(**overrides):
    values = {
        'movimento_email_graph_tenant_id': '',
        'movimento_email_graph_client_id': '',
        'movimento_email_graph_client_secret': '',
        'azure_tenant_id': 'tenant-legado',
        'azure_client_id': 'client-legado',
        'azure_client_secret': 'secret-legado',
        'movimento_email_smtp_host': '',
        'movimento_email_smtp_port': 587,
        'movimento_email_smtp_user': '',
        'movimento_email_smtp_password': '',
        'movimento_email_smtp_use_tls': True,
        'movimento_email_smtp_from': '',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_graph_prefere_identidade_segregada(monkeypatch):
    secrets = {
        'MOVIMENTO_EMAIL_PROVIDER': 'graph',
        'MOVIMENTO_EMAIL_GRAPH_SENDER': 'reports@example.com',
    }
    monkeypatch.setattr(sender_factory, 'get_secret', lambda name, default='': secrets.get(name, default))
    settings = _settings(
        movimento_email_graph_tenant_id='tenant-dedicado',
        movimento_email_graph_client_id='client-dedicado',
        movimento_email_graph_client_secret='secret-dedicado',
    )

    sender, remetente, provider = sender_factory.criar_sender_email_movimento(settings)

    assert isinstance(sender, GraphEmailSender)
    assert provider == 'graph'
    assert remetente == 'reports@example.com'
    assert sender._tenant_id == 'tenant-dedicado'
    assert sender._client_id == 'client-dedicado'
    assert sender._client_secret == 'secret-dedicado'


def test_graph_mantem_fallback_legado_quando_identidade_dedicada_ausente(monkeypatch):
    secrets = {
        'MOVIMENTO_EMAIL_PROVIDER': 'graph',
        'MOVIMENTO_EMAIL_GRAPH_SENDER': 'reports@example.com',
    }
    monkeypatch.setattr(sender_factory, 'get_secret', lambda name, default='': secrets.get(name, default))

    sender, _, _ = sender_factory.criar_sender_email_movimento(_settings())

    assert sender._tenant_id == 'tenant-legado'
    assert sender._client_id == 'client-legado'
    assert sender._client_secret == 'secret-legado'


def test_readiness_graph_bloqueia_identidade_dedicada_parcial(monkeypatch):
    secrets = {
        'MOVIMENTO_EMAIL_PROVIDER': 'graph',
        'MOVIMENTO_EMAIL_GRAPH_SENDER': 'reports@example.com',
    }
    monkeypatch.setattr(sender_factory, 'get_secret', lambda name, default='': secrets.get(name, default))
    settings = _settings(movimento_email_graph_client_id='client-dedicado')

    readiness = sender_factory.avaliar_prontidao_entrega_externa(settings)

    assert readiness == {
        'provider': 'graph',
        'external_delivery_capable': False,
        'reason': 'graph_configuration_incomplete',
    }
