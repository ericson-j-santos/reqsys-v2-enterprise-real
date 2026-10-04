import json
from pathlib import Path


BASE = (
    Path(__file__).resolve().parents[2]
    / 'artifacts'
    / 'lowcode-solution-factory'
    / 'copilot-hitl-agent-network'
)


def _load(relative_path: str) -> dict:
    return json.loads((BASE / relative_path).read_text(encoding='utf-8'))


def test_manifesto_exige_governanca_hitl():
    manifest = _load('manifest.json')

    assert manifest['target'] == 'Microsoft Copilot Studio + Power Automate + Dataverse'
    assert manifest['governance']['human_approval_required'] is True
    assert manifest['governance']['immutable_approval_history'] is True
    assert manifest['governance']['workflow_state_versioning'] is True
    assert manifest['governance']['correlation_id_required'] is True
    assert manifest['governance']['external_writes_require_approval'] is True
    assert manifest['environments'] == ['dev', 'stg', 'prod']


def test_dataverse_possui_estado_transicoes_aprovacoes_e_outbox():
    schema = _load('dataverse/schema.json')
    tables = {table['logical_name']: table for table in schema['tables']}

    required = {
        'reqsys_workflow_instance',
        'reqsys_workflow_transition',
        'reqsys_approval_request',
        'reqsys_agent_execution',
        'reqsys_integration_outbox',
    }
    assert required.issubset(tables)
    assert tables['reqsys_workflow_transition']['append_only'] is True
    assert tables['reqsys_workflow_instance']['alternate_keys'] == ['reqsys_correlation_id']

    workflow_columns = {
        column['name'] for column in tables['reqsys_workflow_instance']['columns']
    }
    assert 'reqsys_state_version' in workflow_columns
    assert 'reqsys_resume_token_hash' in workflow_columns


def test_rede_possui_supervisor_especialistas_e_handoff_versionado():
    agents = _load('copilot/agents.json')

    assert agents['supervisor']['name'] == 'ReqSys Supervisor'
    names = {agent['name'] for agent in agents['specialists']}
    assert {
        'ReqSys Requisitos',
        'ReqSys BDD',
        'ReqSys QA',
        'ReqSys Governança',
        'ReqSys DevOps',
    } == names
    assert agents['handoff_contract']['reject_on_stale_state_version'] is True
    assert 'correlation_id' in agents['handoff_contract']['required_fields']
    assert 'state_version' in agents['handoff_contract']['required_fields']


def test_flows_cobrem_aprovacao_multinivel_retomada_sla_e_integracoes():
    contract = _load('powerautomate/flows.json')
    flows = {flow['name']: flow for flow in contract['flows']}

    assert 'ReqSys HITL - Aprovação Analista' in flows
    assert 'ReqSys HITL - Aprovação Product Owner' in flows
    assert 'ReqSys HITL - Aprovação Gestor' in flows
    assert 'ReqSys HITL - Retomada Pós-Aprovação' in flows
    assert 'ReqSys HITL - Monitor de SLA e Escalonamento' in flows
    assert flows['ReqSys HITL - Retomada Pós-Aprovação']['reject_stale_version'] is True
    assert flows['ReqSys HITL - Dispatcher de Integrações']['idempotent'] is True

    references = set(contract['connection_references'])
    assert 'shared_approvals' in references
    assert 'shared_teams' in references
    assert 'shared_github' in references
    assert 'reqsys_redmine_custom_connector' in references
