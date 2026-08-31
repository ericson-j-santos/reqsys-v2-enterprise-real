import json

import pytest

from app.services.wsjf_planner_excel_provisioning import (
    LOCAL_FIELDS,
    PROFILE,
    TABLE,
    gerar_definicao,
    montar_bundle,
    validar_definicao,
)


def _payload(**overrides):
    data = {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'excel_source': 'groups/group-dev-001',
        'excel_drive': 'drive-dev-001',
        'excel_file': 'arquivo-dev-001',
        'planner_connection_id': 'planner-connection-dev',
        'excel_connection_id': 'excel-connection-dev',
        'target_environment': 'dev',
        'confirmar': False,
        'correlation_id': 'corr-wsjf-test',
    }
    data.update(overrides)
    return data


def _walk(actions):
    for action in actions.values():
        yield action
        nested = action.get('actions')
        if isinstance(nested, dict):
            yield from _walk(nested)
        else_actions = action.get('else', {}).get('actions')
        if isinstance(else_actions, dict):
            yield from _walk(else_actions)


def test_bundle_wsjf_tem_exatamente_um_fluxo_e_tb_demandas():
    bundle = montar_bundle(_payload())

    assert bundle['profile'] == PROFILE
    assert bundle['excel']['table'] == TABLE == 'tbDemandas'
    assert len(bundle['flows']) == 1
    assert bundle['flows'][0]['display_name'] == 'ReqSys WSJF - Planner para Excel'
    assert bundle['excel']['planner_is_source_of_truth'] is True
    assert set(bundle['excel']['local_fields_preserved']) == LOCAL_FIELDS


def test_fluxo_e_horario_e_nao_escreve_no_planner():
    definition = gerar_definicao(_payload())
    recurrence = definition['triggers']['Recorrencia']['recurrence']
    raw = json.dumps(definition, ensure_ascii=False)

    assert recurrence == {'frequency': 'Hour', 'interval': 1}
    assert 'ListTasks_V3' in raw
    assert 'UpdateTask_V2' not in raw
    assert 'UpdateTask_V3' not in raw
    assert validar_definicao(definition) == []


def test_atualizacao_preserva_campos_locais_excel():
    definition = gerar_definicao(_payload())
    patch_items = []
    for action in _walk(definition['actions']):
        host = action.get('inputs', {}).get('host', {})
        if host.get('operationId') == 'PatchItem':
            patch_items.append(action['inputs']['parameters']['item'])

    assert len(patch_items) == 1
    assert LOCAL_FIELDS.isdisjoint(patch_items[0].keys())
    assert patch_items[0]['TaskId'] == "@items('Para_cada_tarefa')?['id']"
    assert 'Sincronizado em' in patch_items[0]


def test_perfil_falha_fechado_fora_de_dev():
    with pytest.raises(ValueError, match='restrito a DEV'):
        montar_bundle(_payload(target_environment='prod'))
