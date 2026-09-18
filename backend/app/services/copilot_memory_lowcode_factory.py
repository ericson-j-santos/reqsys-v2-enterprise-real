from __future__ import annotations

import base64
import json
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

FACTORY_PROFILE_VERSION = '1.1.0'
PACKAGE_NAME = 'copilot-memory-lowcode'

PROFILE_RESTRITO = 'copilot_memory_corporativo_restrito'
PROFILE_COM_API = 'copilot_memory_corporativo_com_api'
PROFILE_MINIMAL_LEGACY = 'copilot_memory_minimal'
PROFILE_ENTERPRISE = 'copilot_memory_enterprise'


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usar_api(profile: str) -> bool:
    return profile in {PROFILE_COM_API, PROFILE_MINIMAL_LEGACY, PROFILE_ENTERPRISE}


def _perfil_efetivo(profile: str) -> str:
    if profile == PROFILE_MINIMAL_LEGACY:
        return PROFILE_COM_API
    return profile


def _connection_references(usar_api: bool) -> list[dict[str, str]]:
    connections = [
        {'name': 'cr_planner', 'connector': 'shared_planner', 'purpose': 'Ler e atualizar tarefas do Planner'},
        {'name': 'cr_excel', 'connector': 'shared_excelonlinebusiness', 'purpose': 'Ler e atualizar a memória corporativa'},
        {'name': 'cr_sharepoint', 'connector': 'shared_sharepointonline', 'purpose': 'Hospedar a planilha corporativa e referências do Copilot'},
    ]
    if usar_api:
        connections.append({
            'name': 'cr_memory_api',
            'connector': 'custom_copilot_memory_api',
            'purpose': 'Acessar a API portátil Copilot Memory',
        })
    return connections


def _environment_variables(usar_api: bool) -> list[dict[str, Any]]:
    variables: list[dict[str, Any]] = [
        {'name': 'PLANNER_PLAN_ID', 'required': True, 'secret': False, 'example': None},
        {'name': 'EXCEL_SITE_URL', 'required': True, 'secret': False, 'example': None},
        {'name': 'EXCEL_FILE_PATH', 'required': True, 'secret': False, 'example': '/Documentos/CopilotMemory.xlsx'},
        {'name': 'SYNC_INTERVAL_MINUTES', 'required': False, 'secret': False, 'default': 15},
    ]
    if usar_api:
        variables[0:0] = [
            {'name': 'COPILOT_MEMORY_API_BASE_URL', 'required': True, 'secret': False, 'example': 'https://memory-api.interno'},
            {'name': 'COPILOT_MEMORY_SERVICE_TOKEN', 'required': True, 'secret': True, 'example': None},
        ]
    return variables


def _excel_contract(usar_api: bool) -> dict[str, Any]:
    workbook_role = (
        'projecao_e_comandos; nao e fonte canonica da memoria'
        if usar_api
        else 'fonte_canonica_da_memoria_e_historico_no_perfil_restrito'
    )
    tables: list[dict[str, Any]] = [
        {
            'sheet': 'Memoria',
            'table': 'tbMemoriaCopilot',
            'key': 'MemoryId',
            'write_owner': 'flow_memory_to_excel' if usar_api else 'power_automate_e_humano_em_campos_de_memoria',
            'columns': [
                'MemoryId', 'PlannerTaskId', 'Assunto', 'Contexto', 'EstadoAtual',
                'Decisao', 'Pendencia', 'ProximoPasso', 'FonteUrl', 'DataFonte',
                'Validade', 'PlannerTitulo', 'PlannerStatus', 'PlannerPercentual',
                'PlannerPrazo', 'Versao', 'ContentHash', 'PlannerSyncStatus',
                'PlannerAppliedSignature', 'CorrelationId', 'AtualizadoEm',
            ],
        },
        {
            'sheet': 'AtualizacoesPlanner',
            'table': 'tbAtualizacoesPlanner',
            'key': 'MemoryId',
            'write_owner': 'humano_ou_fluxo_autorizado',
            'columns': [
                'MemoryId', 'PlannerTaskId', 'PlannerTitulo', 'PlannerStatus',
                'PlannerPercentual', 'PlannerPrazo', 'AtualizarPlanner',
                'SolicitadoPor', 'SolicitadoEm', 'ResultadoSync', 'DetalheConflito',
                'CorrelationId',
            ],
        },
    ]
    if not usar_api:
        tables.append({
            'sheet': 'Historico',
            'table': 'tbHistoricoCopilot',
            'key': 'EventId',
            'write_owner': 'power_automate_append_only',
            'columns': [
                'EventId', 'MemoryId', 'PlannerTaskId', 'Versao', 'Origem',
                'TipoEvento', 'Resumo', 'PlannerSignature', 'CorrelationId', 'CriadoEm',
            ],
        })
    return {
        'workbook_role': workbook_role,
        'tables': tables,
        'loop_guard': (
            'flow Planner->Excel nunca marca AtualizarPlanner=SIM; '
            'flow Excel->Planner só processa SIM explícito e sempre relê o Planner antes de escrever'
        ),
        'concurrency_guard': (
            'se a assinatura atual do Planner divergir de PlannerAppliedSignature durante comando pendente, '
            'marcar conflito e não atualizar o Planner'
        ),
    }


def _flows_com_api() -> list[dict[str, Any]]:
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


def _flows_restrito() -> list[dict[str, Any]]:
    return [
        {
            'id': 'flow_planner_to_excel_memory',
            'name': 'Copilot Memory Restrito - Planner para Excel',
            'trigger': {'type': 'Recurrence', 'default_minutes': 15},
            'connections': ['cr_planner', 'cr_excel', 'cr_sharepoint'],
            'steps': [
                'Listar tarefas do plano configurado',
                'Normalizar PlannerTaskId, titulo, status, percentual e prazo',
                'Montar PlannerSignature determinística com os campos normalizados',
                'Localizar tbMemoriaCopilot por PlannerTaskId',
                'Inserir quando ausente sem sobrescrever campos de memória mantidos por humano',
                'Se houver comando pendente e a assinatura divergir da aplicada, marcar CONFLITO e não sobrescrever',
                'Quando houver mudança válida, incrementar Versao e acrescentar evento em tbHistoricoCopilot',
            ],
            'idempotency': 'PlannerTaskId + comparação determinística de PlannerSignature',
        },
        {
            'id': 'flow_excel_to_planner_restrito',
            'name': 'Copilot Memory Restrito - Excel para Planner',
            'trigger': {'type': 'Recurrence', 'default_minutes': 15},
            'connections': ['cr_excel', 'cr_sharepoint', 'cr_planner'],
            'steps': [
                'Ler tbAtualizacoesPlanner e filtrar AtualizarPlanner=SIM',
                'Reler a tarefa atual do Planner antes de qualquer escrita',
                'Montar assinatura atual e comparar com PlannerAppliedSignature',
                'Se divergir, marcar CONFLITO, preencher DetalheConflito e não atualizar Planner',
                'Se igual, atualizar somente campos autorizados',
                'Atualizar PlannerAppliedSignature, limpar AtualizarPlanner e registrar histórico append-only',
            ],
            'conflict_policy': 'conflito interrompe escrita; nunca aplicar regra ultimo-vence',
            'idempotency': 'MemoryId + PlannerAppliedSignature + flag AtualizarPlanner',
        },
        {
            'id': 'flow_memory_health_restrito',
            'name': 'Copilot Memory Restrito - Saude',
            'trigger': {'type': 'Recurrence', 'default_minutes': 60},
            'connections': ['cr_excel', 'cr_sharepoint'],
            'steps': [
                'Contar PlannerSyncStatus=CONFLITO ou ERRO em tbMemoriaCopilot/tbAtualizacoesPlanner',
                'Registrar correlationId da execução no histórico',
                'Falhar de forma visível quando houver conflitos ou erros acima do limite configurado',
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


def _instalacao(profile: str, usar_api: bool) -> str:
    if not usar_api:
        return f"""# Instalação corporativa — {profile}

1. Criar ou selecionar a planilha corporativa no SharePoint/OneDrive.
2. Criar as tabelas descritas em `excel/tables.json`, incluindo `tbHistoricoCopilot`.
3. Criar somente as referências de conexão do Planner, Excel e SharePoint.
4. Vincular `PLANNER_PLAN_ID`, `EXCEL_SITE_URL`, `EXCEL_FILE_PATH` e o intervalo de sincronização.
5. Importar/criar os flows em DEV.
6. Executar os testes de aceite e validar conflito concorrente antes de promover.
7. Adicionar a planilha como referência do Copilot Notebook.

Este perfil não exige Dataverse, Power Apps, conector personalizado, API Copilot Memory, SQL Server ou permissão administrativa do Power Platform.

Critério de conclusão: criar uma tarefa de teste, sincronizar uma única linha, alterar um campo autorizado via tabela de comandos, repetir o ciclo sem duplicidade e comprovar que alteração concorrente vira CONFLITO sem sobrescrita.
"""
    extra = (
        '\n8. Importar Dataverse/Power App do pacote enterprise em DEV.'
        '\n9. Validar papéis e resolução de conflito.'
        if profile == PROFILE_ENTERPRISE
        else ''
    )
    return f"""# Instalação corporativa — {profile}

1. Implantar `copilot-memory-core`/API no ambiente corporativo.
2. Aplicar o esquema SQL Server do pacote principal.
3. Criar ou selecionar a planilha corporativa e as tabelas descritas em `excel/tables.json`.
4. Criar as referências de conexão do Planner, Excel/SharePoint e Copilot Memory API.
5. Vincular as variáveis do ambiente; segredo deve ficar no cofre/conexão do tenant, nunca no pacote.
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
    effective_profile = _perfil_efetivo(profile)
    usar_api = _usar_api(profile)
    enterprise = profile == PROFILE_ENTERPRISE
    prefix = ''.join(ch for ch in request.owner_prefix.lower() if ch.isalnum() or ch == '_')[:20] or 'memory'
    connections = _connection_references(usar_api)
    environment_variables = _environment_variables(usar_api)
    excel = _excel_contract(usar_api)
    flows = _flows_com_api() if usar_api else _flows_restrito()
    custom_connector = _custom_connector() if usar_api else {}

    memory_history = 'Copilot Memory API/SQL Server' if usar_api else 'Excel/SharePoint (tbMemoriaCopilot + tbHistoricoCopilot)'
    excel_role = 'projection_and_commands' if usar_api else 'canonical_memory_history_and_commands'

    modules = ['powerautomate', 'excel_sharepoint', 'copilot_notebook']
    if usar_api:
        modules.append('copilot_memory_api')
    if enterprise:
        modules.extend(['dataverse', 'powerapps', 'security'])

    solution: dict[str, Any] = {
        'schema_version': FACTORY_PROFILE_VERSION,
        'capability': 'Copilot Memory Low-Code Package',
        'profile': profile,
        'effective_profile': effective_profile,
        'compatibility_alias': profile == PROFILE_MINIMAL_LEGACY,
        'status': 'planned' if request.dry_run else 'ready_for_pipeline',
        'correlation_id': str(uuid.uuid4()),
        'generated_at': _agora(),
        'solution_name': request.solution_name,
        'display_name': request.display_name,
        'description': request.description,
        'target_environment': request.target_environment,
        'modules': modules,
        'publisher': {'name': 'Copilot Memory', 'prefix': prefix},
        'governance': {
            'mode': 'dry_run_blueprint' if request.dry_run else 'alm_pipeline_requested',
            'sandbox_first': True,
            'requires_human_or_pipeline_approval': True,
            'no_custom_reqsys_api_required': True,
            'requires_custom_memory_api': usar_api,
            'requires_dataverse': enterprise,
            'requires_powerapps_admin': enterprise,
            'requires_power_platform_admin': enterprise,
            'source_of_truth': {
                'tasks': 'Planner',
                'memory_history': memory_history,
                'excel': excel_role,
            },
            'secrets_embedded': False,
        },
        'connections': connections,
        'environment_variables': environment_variables,
        'excel': excel,
        'flows': flows,
        'copilot': _copilot_notebook(),
        'custom_connector': custom_connector,
        'dataverse': {'tables': [], 'is_source_of_truth': False},
        'apps': {'canvas_app': {}},
        'security_roles': [],
        'core': {
            'package': 'copilot-memory-core',
            'runtime_required': usar_api,
            'restricted_profile_usage': (
                'opcional para validação/offline; não é dependência de execução do Power Automate'
                if not usar_api
                else 'usado pela API portátil'
            ),
        },
        'alm_package': {
            'requires_approval': True,
            'portable': True,
            'target_environment': request.target_environment,
            'connection_references': [item['name'] for item in connections],
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
        {'path': 'copilot/notebook.json', 'content': json.dumps(solution['copilot'], ensure_ascii=False, indent=2)},
        {'path': 'deployment/INSTALL.md', 'content': _instalacao(profile, usar_api)},
    ]
    if usar_api:
        files.append({
            'path': 'connector/copilot-memory-api.json',
            'content': json.dumps(solution['custom_connector'], ensure_ascii=False, indent=2),
        })
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
    solution['canvas_markdown'] = _instalacao(profile, usar_api)
    return solution
