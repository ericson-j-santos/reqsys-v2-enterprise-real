from unittest.mock import MagicMock, patch

import pytest

from app.services.operational_deploy import executar_deploy_dev, preparar_deploy_dev


def test_preparar_backend_dev_nao_toca_producao():
    op = preparar_deploy_dev('backend')
    assert op.app_name == 'reqsys-api-dev'
    assert op.ambiente == 'development'
    assert op.production_touched is False
    assert len(op.idempotency_key) == 64


def test_preparar_frontend_dev_mapeia_app_canonico():
    op = preparar_deploy_dev('frontend')
    assert op.app_name == 'reqsys-app-dev'


def test_aplicacao_fora_allowlist_e_bloqueada():
    with pytest.raises(ValueError):
        preparar_deploy_dev('production')


def test_execucao_sem_token_falha_fechada():
    with patch('app.services.operational_deploy._token', return_value=''):
        with pytest.raises(RuntimeError, match='Credencial GitHub'):
            executar_deploy_dev('backend')


def test_dispatch_backend_usa_workflow_governado_sem_confirmacao_prod():
    resposta = MagicMock()
    resposta.status_code = 204
    with patch('app.services.operational_deploy._token', return_value='token-teste'):
        with patch('app.services.operational_deploy.requests.post', return_value=resposta) as post:
            resultado = executar_deploy_dev('backend')

    payload = post.call_args.kwargs['json']
    assert payload['ref'] == 'main'
    assert payload['inputs'] == {
        'app_name': 'reqsys-api-dev',
        'environment': 'development',
        'command': 'deploy',
        'scale_count': '1',
        'confirmacao': '',
    }
    assert resultado['status'] == 'EM_EXECUCAO'
    assert resultado['production_touched'] is False
