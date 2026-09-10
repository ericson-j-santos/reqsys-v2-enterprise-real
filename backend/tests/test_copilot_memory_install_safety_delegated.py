import asyncio
from unittest.mock import AsyncMock, patch

from app.services.copilot_memory_install_safety import validar_destino_assistente


def test_validacao_delegada_rele_dev_sem_credencial_app_only():
    delegated = {
        'configurado': True,
        'erro': None,
        'ambientes': [
            {
                'id': '567445cb-49a2-ef0f-8490-cc81a281d6ed',
                'nome': 'ReqSys Dev',
                'url': 'https://orge9b920f1.crm2.dynamics.com',
                'tipo': 'Sandbox',
                'estado': 'Ready',
            }
        ],
    }
    with patch(
        'app.services.copilot_memory_install_safety._listar_ambientes_delegado',
        new=AsyncMock(return_value=delegated),
    ) as delegado_mock, patch(
        'app.services.copilot_memory_install_safety.listar_ambientes_instalacao',
        new=AsyncMock(side_effect=AssertionError('nao deve usar app-only quando ha token delegado')),
    ):
        ambiente = asyncio.run(
            validar_destino_assistente(
                '567445cb-49a2-ef0f-8490-cc81a281d6ed',
                'https://orge9b920f1.crm2.dynamics.com',
                user_token='delegated-token',
            )
        )

    assert ambiente['nome'] == 'ReqSys Dev'
    assert ambiente['tipo'] == 'Sandbox'
    delegado_mock.assert_awaited_once_with('delegated-token')


def test_validacao_delegada_continua_bloqueando_producao():
    delegated = {
        'configurado': True,
        'erro': None,
        'ambientes': [
            {
                'id': 'env-prod-001',
                'nome': 'ReqSys Prod',
                'url': 'https://orgprod.crm2.dynamics.com',
                'tipo': 'Production',
                'estado': 'Ready',
            }
        ],
    }
    with patch(
        'app.services.copilot_memory_install_safety._listar_ambientes_delegado',
        new=AsyncMock(return_value=delegated),
    ):
        try:
            asyncio.run(
                validar_destino_assistente(
                    'env-prod-001',
                    'https://orgprod.crm2.dynamics.com',
                    user_token='delegated-token',
                )
            )
        except ValueError as exc:
            assert 'producao' in str(exc).lower()
        else:
            raise AssertionError('ambiente de producao deveria permanecer bloqueado')
