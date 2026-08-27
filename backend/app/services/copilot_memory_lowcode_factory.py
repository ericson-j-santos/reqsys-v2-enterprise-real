from __future__ import annotations

import base64
import json
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

FACTORY_PROFILE_VERSION = '1.0.0'
PACKAGE_NAME = 'copilot-memory-lowcode'


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connection_references() -> list[dict[str, str]]:
    return [
        {'name': 'cr_planner', 'connector': 'shared_planner', 'purpose': 'Ler e atualizar tarefas do Planner'},
        {'name': 'cr_excel', 'connector': 'shared_excelonlinebusiness', 'purpose': 'Projetar memória e ler solicitações de atualização'},
        {'name': 'cr_sharepoint', 'connector': 'shared_sharepointonline', 'purpose': 'Hospedar a planilha corporativa e referências do Copilot'},
        {'name': 'cr_memory_api', 'connector': 'custom_copilot_memory_api', 'purpose': 'Acessar a API portátil Copilot Memory'},
    ]


def _environment_variables() -> list[dict[str, Any]]:
    return [
        {'name': 'COPILOT_MEMORY_API_BASE_URL', 'required': True, 'secret': False, 'example': 'https://memory-api.interno'},
        {'name': 'COPILOT_MEMORY_SERVICE_TOKEN', 'required': True, 'secret': True, 'example': None},
        {'name': 'PLANNER_PLAN_ID', 'required': True, 'secret': False, 'example': None},
        {'name': 'EXCEL_SITE_URL', 'required': True, 'secret': False, 'example': None},
        {'name': 'EXCEL_FILE_PATH', 'required': True, 'secret': False, 'example': '/Documentos/CopilotMemory.xlsx'},
        {'name': 'SYNC_INTERVAL_MINUTES', 'required': False, 'secret': False, 'default': 15},
    ]


def _excel_contract() -> dict[str, Any]:
    return {
        'workbook_role': 'projecao_e_comandos; nao e fonte canonica da memoria',
        'tables': [
            {
                'sheet': 'Memoria',
                'table': 'tbMemoriaCopilot',
                'key': 'MemoryId',
                'write_owner': 'flow_memory_to_excel',
                'columns': [
                    'MemoryId', 'PlannerTaskId', 'Assunto', 'Contexto', 'EstadoAtual',
                    'Decisao', 'Pendencia', 'ProximoPasso', 'FonteUrl', 'DataFonte',
                    'Validade', 'PlannerTitulo', 'PlannerStatus', 'PlannerPercentual',
                    'PlannerPrazo', 'Versao', 'ContentHash', 'PlannerSyncStatus',
                    'CorrelationId', 'AtualizadoEm',
                ],
            },
            {
                'sheet': 'AtualizacoesPlanner',
                'table': 'tbAtualizacoesPlanner',
                'key': 'MemoryId',
                'write_owner': 'humano_ou_power_app',
                'columns': [
                    'MemoryId', 'PlannerTaskId', 'PlannerTitulo', 'PlannerStatus',
                    'PlannerPercentual', 'PlannerPrazo', 'AtualizarPlanner',
                    'SolicitadoPor', 'SolicitadoEm', 'ResultadoSync', 'CorrelationId',
                ],
            },
        ],
        'loop_guard': 'flow de projeção nunca grava AtualizarPlanner=SIM; flow de comando só processa SIM explícito',
    }


def _flows() -> list[dict[str, Any]]:
    return [
        {
            'id': 'flow_planner_to_memory',
            'name': 'Copilot Memory - Planner para Memoria',
            'trigger': {'type': 'Recurrence', 'default_minutes': 15},
            'connections': ['cr_planner', 'cr_memory_api'],
            'steps': [
                'Listar tarefas do plano configurado',
                'Normalizar taskId, titulo, status, percentual e prazo',
                'POST /v1/hub-lowcode/copilot-memory/sync com origem=planner',
                'Registrar correlationId e falha por item sem interromper o lote inteiro',
            ],
            'idempotency': 'PlannerTaskId + hash de conteúdo calculado pela API',
        },
        {
            'id': 'flow_memory_to_excel',
            'name': 'Copilot Memory - Memoria para Excel',
            'trigger': {'type': 'Recurrence', 'default_minutes': 15},
            'connections': ['cr_memory_api', 'cr_excel', 'cr_sharepoint'],
            'steps': [
                'GET /v1/hub-lowcode/copilot-memory/export',
                'Localizar linha por MemoryId em tbMemoriaCopilot',
                'Inserir quando ausente; atualizar somente quando ContentHash mudou',
                'Nunca escrever AtualizarPlanner na tabela de comandos',
            ],
            'idempotency': 'MemoryId + ContentHash',
        },
        {
            'id': 'flow_excel_to_planner',
            'name': 'Copilot Memory - Excel para Planner',
            'trigger': {'type': 'Recurrence', 'default_minutes': 15},
            'connections': ['cr_excel', 'cr_memory_api', 'cr_planner'],
            'steps': [
                'Ler tbAtualizacoesPlanner e filtrar AtualizarPlanner=SIM',
                'POST /sync com origem=excel e atualizarPlanner=true',
                'GET /planner-commands',
                'Atualizar somente os campos autorizados da tarefa',
                'POST /{memoryId}/planner-ack com sucesso ou erro',
                'Marcar solicitação como processada somente após ack',
            ],
            'conflict_policy': 'conflito interrompe escrita; nunca aplicar regra ultimo-vence',
        },
        {
            'id': 'flow_memory_health',
            'name': 'Copilot Memory - Saude da Sincronizacao',
            'trigger': {'type': 'Recurrence', 'default_minutes': 60},
            'connections': ['cr_memory_api'],
            'steps': [
                'GET /v1/hub-lowcode/copilot-memory/summary',
                'Falhar de forma visível quando houver conflitos ou erros acima do limite configurado',
                'Gerar evidência com correlationId da execução',
            ],
        },
    ]


def _copilot_notebook() -> dict[str, Any]:
    return {
        'target': 'Microsoft 365 Copilot Notebook',
        'reference': 'arquivo Excel corporativo contendo tbMemoriaCopilot',
        'instructions': [
            'Consulte a memória persistente antes de responder sobre decisões, pesquisas ou pendências.',
            'Não repita pesquisa já registrada como válida sem indicar motivo.',
            'Separe informação confirmada, hipótese, informação vencida e pendência.',
            'Preserve decisões anteriores até existir nova evidência explícita.',
            'Sempre apresente fonte e data quando disponíveis.',
            'Nunca trate ausência de registro como confirmação.',
        ],
    }


def _custom_connector() -> dict[str, Any]:
    return {
        'name': 'CopilotMemoryApi',
        'authentication': {
            'type': 'apiKey',
            'header': 'X-Service-Token',
            'value_source': 'COPILOT_MEMORY_SERVICE_TOKEN',
        },
        'base_url_variable': 'COPILOT_MEMORY_API_BASE_URL',
        'operations': [
            {'operationId': 'SyncMemory', 'method': 'POST', 'path': '/v1/hub-lowcode/copilot-memory/sync'},
            {'operationId': 'ExportMemory', 'method': 'GET', 'path': '/v1/hub-lowcode/copilot-memory/export'},
            {'operationId': 'MemorySummary', 'method': 'GET', 'path': '/v1/hub-lowcode/copilot-memory/summary'},
            {'operationId': 'PlannerCommands', 'method': 'GET', 'path': '/v1/hub-lowcode/copilot-memory/planner-commands'},
            {'operationId': 'PlannerAck', 'method': 'POST', 'path': '/v1/hub-lowcode/copilot-memory/{memoryId}/planner-ack'},
        ],
        'note': 'O endereço e o segredo são vinculados no ambiente de destino; nunca são embutidos no pacote.',
    }


def _enterprise_extensions(prefix: str) -> dict[str, Any]:
    return {
        'dataverse': {
            'tables': [
                {
                    'logical_name': f'{prefix}_memorysyncconfig',
                    'display_name': 'Configuração Copilot Memory',
                    'purpose': 'Configuração operacional não secreta por ambiente',
                    'columns': ['Nome', 'Valor', 'Ambiente', 'Ativo'],
                },
                {
                    'logical_name': f'{prefix}_memoryconflict',
                    'display_name': 'Conflitos Copilot Memory',
                    'purpose': 'Fila humana de conflitos sem duplicar a memória canônica',
                    'columns': ['MemoryId', 'PlannerTaskId', 'Resumo', 'Status', 'CorrelationId', 'CriadoEm'],
                },
            ],
            'is_source_of_truth': False,
        },
        'powerapps': {
            'app_type': 'canvas',
            'name': 'Copilot Memory Admin',
            'screens': [
                {'name': 'scrSaude', 'purpose': 'Indicadores de sincronização e erros'},
                {'name': 'scrConflitos', 'purpose': 'Revisão humana de conflitos'},
                {'name': 'scrConfiguracao', 'purpose': 'Parâmetros não secretos do ambiente'},
            ],
        },
        'security_roles': [
            {'name': 'Copilot Memory Operador', 'permissions': ['read_config', 'read_conflicts']},
            {'name': 'Copilot Memory Aprovador', 'permissions': ['read_config', 'read_conflicts', 'resolve_conflicts']},
            {'name': 'Copilot Memory Administrador', 'permissions': ['manage_config', 'read_conflicts', 'resolve_conflicts']},
            {'name': 'Copilot Memory Auditor', 'permissions': ['read_config', 'read_conflicts']},
        ],
    }


def _instalacao(profile: str) -> str:
    extra = '\n8. Importar Dataverse/Power App do pacote enterprise em DEV.\n9. Validar papéis e resolução de conflito.' if profile == 'copilot_memory_enterprise' else ''
    return f"""# Instalação corporativa — {profile}

1. Implantar `copilot-memory-core`/API no ambiente corporativo.
2. Aplicar o esquema SQL Server do pacote principal.
3. Criar ou selecionar a planilha corporativa e as tabelas descritas em `excel/tables.json`.
4. Criar as referências de conexão do Planner, Excel/SharePoint e Copilot Memory API.
5. Vincular as variáveis do ambiente; segredo deve ficar no cofre/connection do tenant, nunca no pacote.
6. Importar/criar os flows em DEV e executar os testes de aceite.
7. Adicionar a planilha como referência do Copilot Notebook.{extra}

Critério de conclusão: criar uma tarefa de teste, sincronizar uma única linha, alterar um campo autorizado via tabela de comandos, confirmar `planner-ack`, repetir o ciclo e comprovar ausência de duplicidade.
"""


def _zip_base64(files: list[dict[str, str]]) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in files:
            archive.writestr(f"{PACKAGE_NAME}/{item['path']}", item['content'])
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def gerar_copilot_memory_lowcode_solution(request: Any) -> dict[str, Any]:
    profile = request.profile
    enterprise = profile == 'copilot_memory_enterprise'
    prefix = ''.join(ch for ch in request.owner_prefix.lower() if ch.isalnum() or ch == '_')[:20] or 'memory'

    solution: dict[str, Any] = {
        'schema_version': FACTORY_PROFILE_VERSION,
        'capability': 'Copilot Memory Low-Code Package',
        'profile': profile,
        'status': 'planned' if request.dry_run else 'ready_for_pipeline',
        'correlation_id': str(uuid.uuid4()),
        'generated_at': _agora(),
        'solution_name': request.solution_name,
        'display_name': request.display_name,
        'description': request.description,
        'target_environment': request.target_environment,
        'modules': ['powerautomate', 'excel_sharepoint', 'copilot_notebook'] + (['dataverse', 'powerapps', 'security'] if enterprise else []),
        'publisher': {'name': 'Copilot Memory', 'prefix': prefix},
        'governance': {
            'mode': 'dry_run_blueprint' if request.dry_run else 'alm_pipeline_requested',
            'sandbox_first': True,
            'requires_human_or_pipeline_approval': True,
            'no_custom_reqsys_api_required': True,
            'source_of_truth': {'tasks': 'Planner', 'memory_history': 'Copilot Memory API/SQL Server', 'excel': 'projection_and_commands'},
            'secrets_embedded': False,
        },
        'connections': _connection_references(),
        'environment_variables': _environment_variables(),
        'excel': _excel_contract(),
        'flows': _flows(),
        'copilot': _copilot_notebook(),
        'custom_connector': _custom_connector(),
        'dataverse': {'tables': [], 'is_source_of_truth': False},
        'apps': {'canvas_app': {}},
        'security_roles': [],
        'alm_package': {
            'requires_approval': True,
            'portable': True,
            'target_environment': request.target_environment,
            'connection_references': [item['name'] for item in _connection_references()],
            'pac_cli_supported': enterprise,
        },
    }

    if enterprise:
        extensions = _enterprise_extensions(prefix)
        solution['dataverse'] = extensions['dataverse']
        solution['apps']['canvas_app'] = extensions['powerapps']
        solution['security_roles'] = extensions['security_roles']

    files = [
        {'path': 'manifest.json', 'content': json.dumps(solution, ensure_ascii=False, indent=2)},
        {'path': 'powerautomate/flows.json', 'content': json.dumps(solution['flows'], ensure_ascii=False, indent=2)},
        {'path': 'excel/tables.json', 'content': json.dumps(solution['excel'], ensure_ascii=False, indent=2)},
        {'path': 'connections/references.json', 'content': json.dumps(solution['connections'], ensure_ascii=False, indent=2)},
        {'path': 'deployment/environment-variables.json', 'content': json.dumps(solution['environment_variables'], ensure_ascii=False, indent=2)},
        {'path': 'connector/copilot-memory-api.json', 'content': json.dumps(solution['custom_connector'], ensure_ascii=False, indent=2)},
        {'path': 'copilot/notebook.json', 'content': json.dumps(solution['copilot'], ensure_ascii=False, indent=2)},
        {'path': 'deployment/INSTALL.md', 'content': _instalacao(profile)},
    ]
    if enterprise:
        files.extend([
            {'path': 'dataverse/schema.json', 'content': json.dumps(solution['dataverse'], ensure_ascii=False, indent=2)},
            {'path': 'powerapps/admin-app.json', 'content': json.dumps(solution['apps']['canvas_app'], ensure_ascii=False, indent=2)},
            {'path': 'security/roles.json', 'content': json.dumps(solution['security_roles'], ensure_ascii=False, indent=2)},
        ])

    files = sorted(files, key=lambda item: PurePosixPath(item['path']).as_posix())
    solution['package'] = {
        'package_name': PACKAGE_NAME,
        'zip_filename': f'{PACKAGE_NAME}-{profile}-{FACTORY_PROFILE_VERSION}.zip',
        'files': [{'path': item['path'], 'size': len(item['content'])} for item in files],
        'zip_base64': _zip_base64(files),
    }
    solution['canvas_markdown'] = _instalacao(profile)
    return solution
