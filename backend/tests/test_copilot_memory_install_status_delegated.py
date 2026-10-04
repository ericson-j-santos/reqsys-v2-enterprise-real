import asyncio
from unittest.mock import AsyncMock, patch

from app.services.copilot_memory_install_assistant import (
    listar_ambientes_instalacao,
    status_assistente_instalacao,
)


def test_status_encaminha_token_delegado_mesmo_sem_app_only():
    resposta = {'configurado': True, 'ambientes': [{'id': 'env-dev'}], 'erro': None}
    with patch(
        'app.services.copilot_memory_install_assistant._credenciais_microsoft_configuradas',
        return_value=False,
    ), patch(
        'app.services.copilot_memory_install_assistant.listar_ambientes_instalacao',
        new=AsyncMock(return_value=resposta),
    ) as listar:
        status = asyncio.run(status_assistente_instalacao(user_token='delegated-token'))

    assert status['microsoft_configurado'] is True
    assert status['ambientes'] == [{'id': 'env-dev'}]
    listar.assert_awaited_once_with(user_token='delegated-token')


class _Resposta:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            'value': [{
                'name': 'env-dev-guid',
                'properties': {
                    'displayName': 'ReqSys Dev',
                    'environmentSku': 'Sandbox',
                    'linkedEnvironmentMetadata': {'instanceUrl': 'https://org-dev.crm2.dynamics.com'},
                },
            }]
        }


class _Cliente:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def get(self, _url, headers):
        assert headers == {'Authorization': 'Bearer delegated-token'}
        return _Resposta()


def test_listagem_de_ambientes_prefere_token_delegado_e_parseia_payload_real():
    with patch('app.services.copilot_memory_install_assistant.httpx.AsyncClient', return_value=_Cliente()), patch(
        'app.services.copilot_memory_install_assistant._token',
        new=AsyncMock(side_effect=AssertionError('app-only nao deve ser chamado')),
    ):
        result = asyncio.run(listar_ambientes_instalacao(user_token='delegated-token'))

    assert result['erro'] is None
    assert result['ambientes'] == [{'id': 'env-dev-guid', 'nome': 'ReqSys Dev', 'url': 'https://org-dev.crm2.dynamics.com', 'estado': '', 'tipo': 'Sandbox', 'regiao': ''}]
