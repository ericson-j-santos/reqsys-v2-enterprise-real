import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_copilot_studio_factory.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.schemas.copilot_studio_solution import CopilotStudioSolutionGenerateRequest
from app.services.copilot_studio_factory import gerar_copilot_studio_solution, montar_arquivos_solution


def test_gerar_copilot_studio_solution_completa():
    solution = gerar_copilot_studio_solution(
        CopilotStudioSolutionGenerateRequest(
            solution_name='ReqSysLowCodeCopilot',
            display_name='ReqSys Copilot Studio',
            target_environment='dev',
            dry_run=True,
        )
    )

    assert solution['capability'] == 'Copilot Studio Multiagent Factory P0'
    assert solution['status'] == 'planned'
    assert solution['governance']['autonomy_level'].startswith('N1')
    assert solution['orchestrator']['child_agents'] == [
        'ReqSys Agente de Demandas',
        'ReqSys Agente de Aprovacoes',
        'ReqSys Agente de Releases',
    ]
    assert set(solution['orchestrator']['system_topics']) == {
        'Fallback', 'MultipleTopicsMatched', 'StartOver', 'Goodbye', 'EndofConversation'
    }
    assert len(solution['agents']) == 3
    assert sum(len(agent['topics']) for agent in solution['agents']) == 4
    assert len(solution['workflows']) == 4
    assert all('correlation_id' in workflow['inputs'] for workflow in solution['workflows'])
    assert len(solution['security_mapping']) == 4
    assert solution['alm_package']['requires_approval'] is True
    assert solution['package']['zip_base64']
    assert 'CANVAS.md' in [item['path'] for item in solution['package']['files']]


def test_topico_de_escrita_exige_confirmacao_e_rbac():
    solution = gerar_copilot_studio_solution(
        CopilotStudioSolutionGenerateRequest(agents=['demandas'])
    )
    demandas = next(agent for agent in solution['agents'] if agent['key'] == 'demandas')
    criar_demanda = next(topic for topic in demandas['topics'] if topic['name'] == 'Criar demanda')
    consultar_status = next(topic for topic in demandas['topics'] if topic['name'] == 'Consultar status')

    assert criar_demanda['confirmation_required'] is True
    assert criar_demanda['rbac_gate'] == ['ReqSys Solicitante', 'ReqSys Administrador Low-Code']
    assert consultar_status['confirmation_required'] is False
    assert consultar_status['rbac_gate'] == []

    workflow = next(item for item in solution['workflows'] if item['invoked_by_topic'] == 'Criar demanda')
    assert workflow['governance']['confirmation_required_before_write'] is True
    assert workflow['governance']['rbac_required'] == ['ReqSys Solicitante', 'ReqSys Administrador Low-Code']


def test_topico_yaml_materializado_contem_gate_e_invoke_flow():
    solution = gerar_copilot_studio_solution(
        CopilotStudioSolutionGenerateRequest(agents=['releases'])
    )
    files = montar_arquivos_solution(solution)
    topic_file = next(item for item in files if item['path'].endswith('resumoderelease.mcs.yml'))

    assert 'kind: AdaptiveDialog' in topic_file['content']
    assert 'triggerQueries:' in topic_file['content']
    assert 'ConditionGroup' in topic_file['content']
    assert 'InvokeFlowAction' in topic_file['content']
    assert 'System.ConversationId' in topic_file['content']


def test_copilot_studio_respeita_agentes_selecionados():
    solution = gerar_copilot_studio_solution(
        CopilotStudioSolutionGenerateRequest(agents=['aprovacoes'], include_alm_package=False)
    )

    assert len(solution['agents']) == 1
    assert solution['agents'][0]['key'] == 'aprovacoes'
    assert len(solution['workflows']) == 1
    assert solution['alm_package'] == {}
