import asyncio

from app.core.config import settings
from app.services.copilot_memory_install_assistant import (
    _compactar_bundle,
    despachar_implantacao,
    montar_bundle_implantacao,
)


def _payload(confirmar=False):
    return {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-12345',
        'plan_id': 'plan-12345',
        'excel_source': 'groups/group-12345',
        'excel_drive': 'drive-12345',
        'excel_file': 'file-12345',
        'planner_connection_id': '/providers/Microsoft.PowerApps/apis/shared_planner/connections/planner-1',
        'excel_connection_id': '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness/connections/excel-1',
        'target_environment': 'dev',
        'confirmar': confirmar,
        'correlation_id': 'cid-install-001',
    }


def test_bundle_tem_tres_fluxos_com_parametros_escolhidos():
    bundle = montar_bundle_implantacao(_payload())

    assert bundle['correlation_id'] == 'cid-install-001'
    assert len(bundle['flows']) == 3
    assert len({flow['flow_guid'] for flow in bundle['flows']}) == 3
    for flow in bundle['flows']:
        params = flow['definition']['parameters']
        assert params['PLANNER_GROUP_ID']['defaultValue'] == 'group-12345'
        assert params['PLANNER_PLAN_ID']['defaultValue'] == 'plan-12345'
        assert params['EXCEL_DRIVE']['defaultValue'] == 'drive-12345'
        assert params['EXCEL_FILE']['defaultValue'] == 'file-12345'
        assert flow['state'] == 'Stopped'


def test_bundle_comprimido_cabe_no_dispatch_do_github():
    encoded = _compactar_bundle(montar_bundle_implantacao(_payload()))
    assert len(encoded) < 60000


def test_validacao_nao_despacha_nem_exige_github_pat(monkeypatch):
    monkeypatch.setattr(settings, 'github_pat', '')

    result = asyncio.run(despachar_implantacao(_payload(confirmar=False)))

    assert result['dispatched'] is False
    assert result['status'] == 'aguardando_confirmacao'
    assert len(result['bundle']['flows']) == 3


def test_implantacao_sem_executor_configurado_falha_fechado(monkeypatch):
    monkeypatch.setattr(settings, 'github_pat', '')

    result = asyncio.run(despachar_implantacao(_payload(confirmar=True)))

    assert result == {
        'dispatched': False,
        'status': 'pending_configuration',
        'erro': 'GITHUB_PAT nao configurado no ReqSys',
    }
