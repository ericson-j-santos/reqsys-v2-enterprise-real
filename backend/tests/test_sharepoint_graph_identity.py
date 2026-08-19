from datetime import datetime, timezone

import pytest

from app.core.identity_governance import IdentityGovernanceError
from app.services import sharepoint_graph_identity as module


def test_sharepoint_identity_resolve_contexto_exato(monkeypatch):
    class Profile:
        name = 'sp-dev-confidential'
        environment = 'development'
        tenant_id = 'tenant-sp'
        client_id = 'client-sharepoint-12345678'
        current_secret_ref = 'env://REQSYS_SP_SECRET'
        rotation_due_at = datetime(2026, 9, 1, tzinfo=timezone.utc)

        def requires_rotation(self, now=None):
            return False

    class Registry:
        def resolve(self, *, environment, purpose, data_classification, now=None):
            assert environment == 'development'
            assert purpose == 'sharepoint-package-catalog-read'
            assert data_classification.value == 'confidential'
            return Profile()

    monkeypatch.setattr(module.ApplicationIdentityRegistry, 'from_environment', classmethod(lambda cls: Registry()))
    monkeypatch.setattr(module.settings, 'app_environment', 'development')
    monkeypatch.setenv('REQSYS_SP_SECRET', 'segredo-teste')

    identity = module.resolve_sharepoint_graph_identity()

    assert identity.profile_name == 'sp-dev-confidential'
    assert identity.client_secret == 'segredo-teste'
    assert identity.evidence()['client_id_suffix'] == '12345678'
    assert 'client_secret' not in identity.evidence()


def test_sharepoint_identity_falha_fechada_sem_perfil(monkeypatch):
    class Registry:
        def resolve(self, **kwargs):
            raise IdentityGovernanceError('perfil SharePoint ausente')

    monkeypatch.setattr(module.ApplicationIdentityRegistry, 'from_environment', classmethod(lambda cls: Registry()))

    status = module.sharepoint_graph_identity_status()

    assert status['configured'] is False
    assert 'perfil SharePoint ausente' in status['error']


@pytest.mark.asyncio
async def test_sharepoint_token_nao_aceita_resposta_sem_access_token(monkeypatch):
    class Identity:
        tenant_id = 'tenant'
        client_id = 'client'
        client_secret = 'secret'

    monkeypatch.setattr(module, 'resolve_sharepoint_graph_identity', lambda now=None: Identity())

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda timeout=10: Client())

    with pytest.raises(IdentityGovernanceError, match='access_token'):
        await module.acquire_sharepoint_graph_token()
