from __future__ import annotations

import base64
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from app.schemas.copilot_studio_solution import CopilotStudioSolutionGenerateRequest

FACTORY_VERSION = '0.1.0'
PACKAGE_NAME = 'reqsys-copilot-studio-multiagent'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    normalized = re.sub(r'[^a-zA-Z0-9_]+', '_', value.strip()).strip('_').lower()
    return normalized or 'reqsys'


def _topic_yaml(topic: dict[str, Any], workflow: dict[str, Any] | None) -> str:
    lines = [
        'mcs.metadata:',
        f"  componentName: {_slug(topic['name']).replace('_', '')}",
        f"  description: {topic['description']}",
        'kind: AdaptiveDialog',
        'beginDialog:',
        '  kind: OnRecognizedIntent',
        '  id: main',
        '  intent:',
        f"    displayName: {_slug(topic['name']).replace('_', '')}",
        '    triggerQueries:',
    ]
    lines.extend(f'      - "{query}"' for query in topic['trigger_queries'])
    lines.append('  actions:')
    action_index = 1
    for slot in topic.get('slots', []):
        lines.extend([
            '    - kind: Question',
            f'      id: question_{action_index}',
            f"      variable: Topic.{slot['variable']}",
            f"      prompt: \"{slot['prompt']}\"",
            f"      entity: {slot.get('entity', 'StringPrebuiltEntity')}",
        ])
        action_index += 1

    roles = topic.get('rbac_gate', [])
    if roles:
        condition = ' && '.join(f'User.Papel <> "{role}"' for role in roles)
        lines.extend([
            '    - kind: ConditionGroup',
            f'      id: conditionGroup_{action_index}',
            '      conditions:',
            f'        - id: conditionItem_{action_index + 1}',
            f'          condition: ={condition}',
            '          actions:',
            '            - kind: SendActivity',
            f'              id: sendMessage_{action_index + 2}',
            f'              activity: Acao nao autorizada. Papel minimo exigido: {" ou ".join(roles)}.',
            '            - kind: EndDialog',
            f'              id: endDialog_{action_index + 3}',
            '      elseActions:',
        ])
        indent = '        '
        action_index += 4
    else:
        indent = '    '

    if topic.get('confirmation_required'):
        lines.extend([
            f'{indent}- kind: Question',
            f'{indent}  id: question_{action_index}',
            f'{indent}  variable: Topic.Confirmacao',
            f'{indent}  prompt: "Confirma a execucao de {topic["name"].lower()}? (sim/nao)"',
            f'{indent}  entity: BooleanPrebuiltEntity',
        ])
        action_index += 1

    if workflow:
        lines.extend([
            f'{indent}- kind: InvokeFlowAction',
            f'{indent}  id: invokeFlow_{action_index}',
            f'{indent}  flow: {workflow["logical_name"]}',
            f'{indent}  input:',
        ])
        for name, expression in workflow['topic_inputs'].items():
            lines.append(f'{indent}    {name}: {expression}')
        lines.extend([
            f'{indent}    correlation_id: =System.ConversationId',
            f'{indent}  output:',
            f'{indent}    resultado: Topic.ResultadoFlow',
        ])
        action_index += 1

    lines.extend([
        f'{indent}- kind: SendActivity',
        f'{indent}  id: sendMessage_{action_index}',
        f'{indent}  activity: "{topic["success_message"]}"',
    ])
    return '\n'.join(lines) + '\n'


def _agent_yaml(agent: dict[str, Any], owner_prefix: str) -> str:
    topic_names = ', '.join(topic['name'] for topic in agent['topics'])
    return (
        'kind: GptComponentMetadata\n'
        f"displayName: {agent['display_name']}\n"
        f"description: {agent['description']}\n"
        'language: pt-BR\n'
        f"publisherPrefix: {owner_prefix}\n"
        f"instructions: {agent['instructions']}\n"
        f"topics: {topic_names}\n"
    )


def _definitions(owner_prefix: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    workflows = [
        {
            'key': 'criar_demanda',
            'name': 'ReqSys Intake de Demanda',
            'logical_name': f'{owner_prefix}_ReqSysIntakeDeDemanda',
            'invoked_by_topic': 'Criar demanda',
            'inputs': ['titulo', 'resultado_esperado', 'origem', 'correlation_id'],
            'topic_inputs': {
                'titulo': '=Topic.Titulo',
                'resultado_esperado': '=Topic.ResultadoEsperado',
                'origem': '=Topic.Origem',
            },
            'governance': {
                'confirmation_required_before_write': True,
                'rbac_required': ['ReqSys Solicitante', 'ReqSys Administrador Low-Code'],
                'idempotency_key': 'correlation_id',
                'retry_policy': 'exponential',
            },
        },
        {
            'key': 'consultar_status',
            'name': 'ReqSys Consultar Status',
            'logical_name': f'{owner_prefix}_ReqSysConsultarStatus',
            'invoked_by_topic': 'Consultar status',
            'inputs': ['referencia', 'correlation_id'],
            'topic_inputs': {'referencia': '=Topic.Referencia'},
            'governance': {
                'confirmation_required_before_write': False,
                'rbac_required': [],
                'idempotency_key': 'correlation_id',
                'retry_policy': 'exponential',
            },
        },
        {
            'key': 'preparar_aprovacao',
            'name': 'ReqSys Preparar Aprovacao',
            'logical_name': f'{owner_prefix}_ReqSysPrepararAprovacao',
            'invoked_by_topic': 'Preparar aprovacao',
            'inputs': ['referencia', 'correlation_id'],
            'topic_inputs': {'referencia': '=Topic.Referencia'},
            'governance': {
                'confirmation_required_before_write': True,
                'rbac_required': ['ReqSys Aprovador', 'ReqSys Administrador Low-Code'],
                'idempotency_key': 'correlation_id',
                'retry_policy': 'exponential',
            },
        },
        {
            'key': 'resumo_release',
            'name': 'ReqSys Release Governance',
            'logical_name': f'{owner_prefix}_ReqSysReleaseGovernance',
            'invoked_by_topic': 'Resumo de release',
            'inputs': ['versao', 'correlation_id'],
            'topic_inputs': {'versao': '=Topic.Versao'},
            'governance': {
                'confirmation_required_before_write': True,
                'rbac_required': ['ReqSys Administrador Low-Code'],
                'idempotency_key': 'correlation_id',
                'retry_policy': 'exponential',
            },
        },
    ]
    wf_by_topic = {item['invoked_by_topic']: item for item in workflows}
    agents = [
        {
            'key': 'demandas',
            'display_name': 'ReqSys Agente de Demandas',
            'description': 'Registra e consulta demandas governadas.',
            'instructions': 'Atue somente no dominio de demandas e preserve rastreabilidade.',
            'topics': [
                {
                    'name': 'Criar demanda',
                    'description': 'Registrar nova solicitacao como demanda governada no Dataverse',
                    'trigger_queries': ['quero registrar uma demanda', 'preciso abrir uma solicitacao', 'criar nova demanda', 'abrir demanda no reqsys'],
                    'slots': [
                        {'variable': 'Titulo', 'prompt': 'Qual o titulo da demanda?'},
                        {'variable': 'ResultadoEsperado', 'prompt': 'Qual o resultado esperado?'},
                        {'variable': 'Origem', 'prompt': 'Qual a origem (power_app, teams, copilot, importacao, manual)?'},
                    ],
                    'confirmation_required': True,
                    'rbac_gate': ['ReqSys Solicitante', 'ReqSys Administrador Low-Code'],
                    'success_message': 'Demanda registrada com sucesso. Numero: {Topic.ResultadoFlow.numero_demanda}. Correlation-Id: {System.ConversationId}',
                },
                {
                    'name': 'Consultar status',
                    'description': 'Consultar status de demanda ou requisito',
                    'trigger_queries': ['consultar status da demanda', 'como esta minha solicitacao', 'ver andamento do requisito'],
                    'slots': [{'variable': 'Referencia', 'prompt': 'Informe o numero ou referencia.'}],
                    'confirmation_required': False,
                    'rbac_gate': [],
                    'success_message': 'Status: {Topic.ResultadoFlow.status}. Correlation-Id: {System.ConversationId}',
                },
            ],
        },
        {
            'key': 'aprovacoes',
            'display_name': 'ReqSys Agente de Aprovacoes',
            'description': 'Prepara contexto de aprovacao sem substituir a decisao humana.',
            'instructions': 'Nunca aprove automaticamente. Gere resumo e preserve decisao humana.',
            'topics': [
                {
                    'name': 'Preparar aprovacao',
                    'description': 'Preparar resumo rastreavel para aprovacao humana',
                    'trigger_queries': ['preparar aprovacao', 'gerar resumo para aprovador', 'enviar para aprovacao'],
                    'slots': [{'variable': 'Referencia', 'prompt': 'Informe a referencia da demanda ou requisito.'}],
                    'confirmation_required': True,
                    'rbac_gate': ['ReqSys Aprovador', 'ReqSys Administrador Low-Code'],
                    'success_message': 'Resumo preparado. Decisao final permanece humana. Correlation-Id: {System.ConversationId}',
                },
            ],
        },
        {
            'key': 'releases',
            'display_name': 'ReqSys Agente de Releases',
            'description': 'Consolida evidencias e recomenda go/no-go.',
            'instructions': 'Nunca promova release automaticamente. Decisao final humana.',
            'topics': [
                {
                    'name': 'Resumo de release',
                    'description': 'Consolidar evidencias e gerar recomendacao go/no-go de release, sem decidir automaticamente',
                    'trigger_queries': ['gerar go ou no go', 'resumo executivo do release', 'posso liberar essa release', 'status de release'],
                    'slots': [{'variable': 'Versao', 'prompt': 'Qual a versao do release?'}],
                    'confirmation_required': True,
                    'rbac_gate': ['ReqSys Administrador Low-Code'],
                    'success_message': 'Recomendacao para {Topic.Versao}: {Topic.ResultadoFlow.recomendacao}. Decisao final permanece humana.',
                },
            ],
        },
    ]
    for agent in agents:
        for topic in agent['topics']:
            topic['workflow_key'] = wf_by_topic[topic['name']]['key']
    return agents, workflows


def _canvas(solution: dict[str, Any]) -> str:
    lines = [
        f"# Canvas da Solucao Multiagente — {solution['display_name']}",
        '',
        f"- Ambiente alvo: `{solution['target_environment']}`",
        f"- Correlation ID: `{solution['correlation_id']}`",
        f"- Autonomia: `{solution['governance']['autonomy_level']}`",
        '',
        '## Orquestrador',
        f"- {solution['orchestrator']['display_name']}",
        '',
        '## Agentes especialistas',
    ]
    lines.extend(f"- {agent['display_name']}: {len(agent['topics'])} topico(s)" for agent in solution['agents'])
    lines.extend([
        '',
        '## Guardrails',
        '- Confirmacao humana antes de escrita.',
        '- RBAC por security role.',
        '- correlation_id em todos os workflows.',
        '- Sem decisao automatica de aprovacao ou release.',
    ])
    return '\n'.join(lines) + '\n'


def montar_arquivos_solution(solution: dict[str, Any]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    if solution.get('canvas_markdown'):
        files.append({'path': 'CANVAS.md', 'content': solution['canvas_markdown']})
    files.append({'path': 'manifest.json', 'content': json.dumps({k: v for k, v in solution.items() if k != 'package'}, ensure_ascii=False, indent=2)})
    files.append({'path': 'security/security-mapping.json', 'content': json.dumps(solution['security_mapping'], ensure_ascii=False, indent=2)})
    files.append({'path': 'workflows/flows.json', 'content': json.dumps(solution['workflows'], ensure_ascii=False, indent=2)})
    if solution.get('alm_package'):
        files.append({'path': 'alm/package-plan.json', 'content': json.dumps(solution['alm_package'], ensure_ascii=False, indent=2)})

    owner_prefix = solution['owner_prefix']
    workflow_by_key = {item['key']: item for item in solution['workflows']}
    for agent in solution['agents']:
        agent_slug = _slug(agent['display_name'])
        files.append({
            'path': f'copilot-workspace/agents/{agent_slug}/agent.mcs.yml',
            'content': _agent_yaml(agent, owner_prefix),
        })
        for topic in agent['topics']:
            files.append({
                'path': f"copilot-workspace/agents/{agent_slug}/topics/{_slug(topic['name']).replace('_', '')}.mcs.yml",
                'content': _topic_yaml(topic, workflow_by_key.get(topic['workflow_key'])),
            })

    orchestrator = solution['orchestrator']
    files.append({
        'path': 'copilot-workspace/orchestrator/agent.mcs.yml',
        'content': (
            'kind: GptComponentMetadata\n'
            f"displayName: {orchestrator['display_name']}\n"
            'language: pt-BR\n'
            'instructions: Classifique a intencao e faca handoff para o agente especialista. Nunca execute escrita externa diretamente.\n'
        ),
    })
    for name in orchestrator['system_topics']:
        files.append({
            'path': f'copilot-workspace/orchestrator/topics/{name}.mcs.yml',
            'content': f'mcs.metadata:\n  componentName: {name}\nkind: AdaptiveDialog\n',
        })
    return sorted(files, key=lambda item: item['path'])


def _zip_base64(files: list[dict[str, str]]) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.writestr(item['path'], item['content'])
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def gerar_copilot_studio_solution(request: CopilotStudioSolutionGenerateRequest) -> dict[str, Any]:
    agents, workflows = _definitions(request.owner_prefix)
    selected = set(request.agents)
    agents = [agent for agent in agents if agent['key'] in selected]
    selected_topics = {topic['name'] for agent in agents for topic in agent['topics']}
    workflows = [workflow for workflow in workflows if workflow['invoked_by_topic'] in selected_topics]

    correlation_id = str(uuid.uuid4())
    security_mapping = [
        {'topic': topic['name'], 'roles': topic['rbac_gate']}
        for agent in agents
        for topic in agent['topics']
    ]
    solution: dict[str, Any] = {
        'capability': 'Copilot Studio Multiagent Factory P0',
        'factory_version': FACTORY_VERSION,
        'status': 'planned' if request.dry_run else 'ready_for_provisioning',
        'generated_at': _utc_now(),
        'correlation_id': correlation_id,
        'solution_name': request.solution_name,
        'display_name': request.display_name,
        'description': request.description,
        'target_environment': request.target_environment,
        'owner_prefix': request.owner_prefix,
        'dry_run': request.dry_run,
        'governance': {
            'autonomy_level': 'N1 - assistivo com decisao humana',
            'human_approval_required': True,
            'external_writes_by_orchestrator': False,
            'correlation_id_required': True,
        },
        'orchestrator': {
            'display_name': f'{request.display_name} Orquestrador',
            'child_agents': [agent['display_name'] for agent in agents],
            'system_topics': ['Fallback', 'MultipleTopicsMatched', 'StartOver', 'Goodbye', 'EndofConversation'],
        },
        'agents': agents,
        'workflows': workflows,
        'security_mapping': security_mapping,
        'alm_package': {
            'package_name': PACKAGE_NAME,
            'solution_name': request.solution_name,
            'target_environment': request.target_environment,
            'requires_approval': True,
            'deployment_order': ['dev', 'stg', 'prod'],
            'rollback_required': True,
        } if request.include_alm_package else {},
    }
    solution['canvas_markdown'] = _canvas(solution) if request.include_canvas_markdown else ''
    files = montar_arquivos_solution(solution)
    solution['package'] = {
        'name': PACKAGE_NAME,
        'format': 'zip_base64',
        'files': [{'path': item['path'], 'size_bytes': len(item['content'].encode('utf-8'))} for item in files],
        'zip_base64': _zip_base64(files),
    }
    return solution
