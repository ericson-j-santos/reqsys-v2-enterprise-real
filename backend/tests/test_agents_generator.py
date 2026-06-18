import base64
import io
import json
import zipfile

from app.core.config import settings
from app.services import copilot_studio_provisioner


def test_catalogo_agents_expoe_orquestrador(client):
    resp = client.get('/v1/agents/catalog')

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['orchestrator']['name'] == 'Orquestrador de Software'
    assert len(data['specialists']) >= 10


def test_generate_agents_cria_pacote_copilot_studio(client):
    resp = client.post('/v1/agents/generate', json={
        'name': 'Orquestrador ReqSys',
        'package_type': 'software_lifecycle_orchestrator',
        'target': 'copilot_studio',
        'language': 'pt-BR',
        'include_specialists': True,
        'include_playbook': True,
        'include_zip_base64': True,
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['package_name'] == 'software-lifecycle-agents'
    assert data['zip_filename'] == 'software-lifecycle-agents.zip'
    assert data['total_files'] == 5

    paths = {file['path'] for file in data['files']}
    assert 'README.md' in paths
    assert 'copilot-studio/software-lifecycle-orchestrator.md' in paths
    assert 'copilot-studio/specialist-agents.md' in paths
    assert 'copilot-studio/delivery-playbook.md' in paths
    assert 'copilot-studio/agent-catalog.json' in paths

    catalog_file = next(file for file in data['files'] if file['path'] == 'copilot-studio/agent-catalog.json')
    catalog = json.loads(catalog_file['content'])
    assert catalog['orchestrator']['name'] == 'Orquestrador ReqSys'

    zip_bytes = base64.b64decode(data['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())

    assert 'software-lifecycle-agents/README.md' in names
    assert 'software-lifecycle-agents/copilot-studio/software-lifecycle-orchestrator.md' in names
    assert 'software-lifecycle-agents/copilot-studio/agent-catalog.json' in names


def test_generate_agents_permite_pacote_minimo_sem_zip(client):
    resp = client.post('/v1/agents/generate', json={
        'include_specialists': False,
        'include_playbook': False,
        'include_zip_base64': False,
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['total_files'] == 3
    assert data['zip_base64'] is None

    paths = {file['path'] for file in data['files']}
    assert 'copilot-studio/specialist-agents.md' not in paths
    assert 'copilot-studio/delivery-playbook.md' not in paths


def test_generate_agents_zip_download(client):
    resp = client.post('/v1/agents/generate.zip', json={
        'name': 'Orquestrador Download',
        'include_specialists': True,
        'include_playbook': False,
    })

    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'application/zip'
    assert 'software-lifecycle-agents.zip' in resp.headers['content-disposition']

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        orchestrator = zf.read(
            'software-lifecycle-agents/copilot-studio/software-lifecycle-orchestrator.md'
        ).decode('utf-8')

    assert 'software-lifecycle-agents/README.md' in names
    assert 'software-lifecycle-agents/copilot-studio/specialist-agents.md' in names
    assert 'software-lifecycle-agents/copilot-studio/delivery-playbook.md' not in names
    assert 'Orquestrador Download' in orchestrator


def test_provision_copilot_studio_dry_run(client):
    resp = client.post('/v1/agents/provision/copilot-studio', json={
        'name': 'Orquestrador Dry Run',
        'mode': 'dry_run',
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configured'] is True
    assert data['provisioned'] is False
    assert data['mode'] == 'dry_run'
    assert 'generated_files' in data['details']


def test_provision_copilot_studio_webhook_sem_configuracao(client, monkeypatch):
    monkeypatch.setattr(settings, 'copilotstudio_provisioning_webhook_url', '')

    resp = client.post('/v1/agents/provision/copilot-studio', json={
        'name': 'Orquestrador Webhook',
        'mode': 'webhook',
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configured'] is False
    assert data['provisioned'] is False
    assert data['details']['expected_setting'] == 'COPILOTSTUDIO_PROVISIONING_WEBHOOK_URL'


def test_provision_copilot_studio_webhook_mockado(client, monkeypatch):
    monkeypatch.setattr(settings, 'copilotstudio_provisioning_webhook_url', 'https://flow.example.test/copilot')
    monkeypatch.setattr(settings, 'copilotstudio_provisioning_webhook_key', 'key-test')

    class FakeResponse:
        status_code = 202
        text = '{"accepted": true}'

        def raise_for_status(self):
            return None

        def json(self):
            return {'accepted': True, 'requestId': 'req-123'}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            assert url == 'https://flow.example.test/copilot'
            assert headers['x-api-key'] == 'key-test'
            assert json['agent']['name'] == 'Orquestrador Webhook'
            assert json['package']['package_name'] == 'software-lifecycle-agents'
            return FakeResponse()

    monkeypatch.setattr(copilot_studio_provisioner.httpx, 'AsyncClient', FakeClient)

    resp = client.post('/v1/agents/provision/copilot-studio', json={
        'name': 'Orquestrador Webhook',
        'mode': 'webhook',
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configured'] is True
    assert data['provisioned'] is True
    assert data['details']['webhook_response']['requestId'] == 'req-123'


def test_provision_dataverse_sem_solution_zip_nao_importa(client, monkeypatch):
    monkeypatch.setattr(settings, 'copilotstudio_environment_url', 'https://orgtest.crm2.dynamics.com/')
    monkeypatch.setattr(settings, 'azure_tenant_id', 'tenant')
    monkeypatch.setattr(settings, 'azure_client_id', 'client')
    monkeypatch.setattr(settings, 'azure_client_secret', 'secret')

    resp = client.post('/v1/agents/provision/copilot-studio', json={
        'name': 'Orquestrador Dataverse',
        'mode': 'dataverse_import',
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configured'] is True
    assert data['provisioned'] is False
    assert 'solution_zip_base64' in data['message']
