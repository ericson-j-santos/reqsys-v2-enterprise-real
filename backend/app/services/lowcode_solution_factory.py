from __future__ import annotations

import base64
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from app.core.config import settings
from app.schemas.lowcode_solution import LowCodeSolutionGenerateRequest
from app.services.teams_notification_solution_factory import gerar_teams_notification_solution

FACTORY_VERSION = '0.2.0'
PACKAGE_NAME = 'reqsys-lowcode-solution'
_MD_BR = '  '


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _logical(value: str) -> str:
    normalized = re.sub(r'[^a-zA-Z0-9_]+', '_', value.strip()).strip('_').lower()
    return normalized or 'reqsyslowcode'


def _table(prefix: str, name: str, display: str, description: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
    logical = f'{prefix}_{_logical(name)}'
    base_columns = [
        {'name': f'{prefix}_codigo', 'type': 'text', 'required': True, 'max_length': 80, 'display_name': 'Codigo'},
        {'name': f'{prefix}_titulo', 'type': 'text', 'required': True, 'max_length': 250, 'display_name': 'Titulo'},
        {'name': f'{prefix}_status', 'type': 'choice', 'required': True, 'display_name': 'Status'},
        {'name': f'{prefix}_prioridade', 'type': 'choice', 'required': False, 'display_name': 'Prioridade'},
    ]
    return {
        'logical_name': logical,
        'display_name': display,
        'description': description,
        'ownership': 'UserOrTeam',
        'auditing_enabled': True,
        'change_tracking_enabled': True,
        'columns': base_columns + columns,
        'views': [
            {'name': 'Ativos', 'filter': f'{prefix}_status ne "arquivado"'},
            {'name': 'Pendentes de aprovacao', 'filter': f'{prefix}_status eq "em_aprovacao"'},
            {'name': 'Risco alto', 'filter': f'{prefix}_prioridade eq "alta"'},
        ],
        'forms': [{'name': 'Principal', 'type': 'main'}, {'name': 'Rapido', 'type': 'quick_create'}],
    }


def _dataverse_schema(prefix: str) -> dict[str, Any]:
    tables = [
        _table(prefix, 'demanda', 'Demandas', 'Entrada governada de demandas, ideias e solicitacoes.', [
            {'name': f'{prefix}_origem', 'type': 'choice', 'display_name': 'Origem'},
            {'name': f'{prefix}_solicitante', 'type': 'lookup', 'target': 'systemuser', 'display_name': 'Solicitante'},
            {'name': f'{prefix}_resultado_esperado', 'type': 'multiline_text', 'display_name': 'Resultado esperado'},
            {'name': f'{prefix}_score_priorizacao', 'type': 'whole_number', 'display_name': 'Score de priorizacao'},
        ]),
        _table(prefix, 'requisito', 'Requisitos', 'Requisitos funcionais, nao funcionais, regras e criterios.', [
            {'name': f'{prefix}_demanda_id', 'type': 'lookup', 'target': f'{prefix}_demanda', 'display_name': 'Demanda'},
            {'name': f'{prefix}_tipo', 'type': 'choice', 'display_name': 'Tipo'},
            {'name': f'{prefix}_criterios_aceite', 'type': 'multiline_text', 'display_name': 'Criterios de aceite'},
            {'name': f'{prefix}_regra_negocio', 'type': 'multiline_text', 'display_name': 'Regra de negocio'},
        ]),
        _table(prefix, 'aprovacao', 'Aprovacoes', 'Decisoes formais sobre demandas, requisitos e releases.', [
            {'name': f'{prefix}_referencia', 'type': 'text', 'display_name': 'Referencia'},
            {'name': f'{prefix}_aprovador', 'type': 'lookup', 'target': 'systemuser', 'display_name': 'Aprovador'},
            {'name': f'{prefix}_parecer', 'type': 'multiline_text', 'display_name': 'Parecer'},
            {'name': f'{prefix}_decidido_em', 'type': 'datetime', 'display_name': 'Decidido em'},
        ]),
        _table(prefix, 'evidencia', 'Evidencias', 'Evidencias de qualidade, operacao, release e governanca.', [
            {'name': f'{prefix}_referencia', 'type': 'text', 'display_name': 'Referencia'},
            {'name': f'{prefix}_tipo_evidencia', 'type': 'choice', 'display_name': 'Tipo de evidencia'},
            {'name': f'{prefix}_url', 'type': 'url', 'display_name': 'URL'},
            {'name': f'{prefix}_conteudo', 'type': 'multiline_text', 'display_name': 'Conteudo'},
        ]),
        _table(prefix, 'release', 'Releases', 'Pacotes de mudanca, go/no-go, comunicacao e rollback.', [
            {'name': f'{prefix}_versao', 'type': 'text', 'display_name': 'Versao'},
            {'name': f'{prefix}_janela', 'type': 'datetime', 'display_name': 'Janela'},
            {'name': f'{prefix}_rollback', 'type': 'multiline_text', 'display_name': 'Plano de rollback'},
            {'name': f'{prefix}_go_no_go', 'type': 'choice', 'display_name': 'Go/No-Go'},
        ]),
    ]
    return {
        'tables': tables,
        'relationships': [
            {'from': f'{prefix}_requisito', 'to': f'{prefix}_demanda', 'type': 'many_to_one'},
            {'from': f'{prefix}_aprovacao', 'to': f'{prefix}_demanda', 'type': 'many_to_one'},
            {'from': f'{prefix}_evidencia', 'to': f'{prefix}_release', 'type': 'many_to_one'},
        ],
        'choices': {
            'status': ['novo', 'em_triagem', 'em_aprovacao', 'aprovado', 'em_execucao', 'validado', 'arquivado'],
            'prioridade': ['baixa', 'media', 'alta', 'critica'],
            'origem': ['power_app', 'teams', 'copilot', 'importacao', 'manual'],
            'tipo_requisito': ['funcional', 'nao_funcional', 'regra_negocio', 'integracao', 'seguranca'],
        },
    }


def _canvas_app(prefix: str, solution_name: str) -> dict[str, Any]:
    screens = [
        {'name': 'scrDashboard', 'title': 'Painel ReqSys', 'purpose': 'Resumo operacional com demandas, aprovacoes, riscos e releases.', 'data_sources': [f'{prefix}_demanda', f'{prefix}_aprovacao', f'{prefix}_release'], 'components': ['Header', 'KpiStrip', 'DemandasRecentes', 'AprovacoesPendentes', 'ReleaseStatus']},
        {'name': 'scrDemandas', 'title': 'Demandas', 'purpose': 'Criar, classificar e acompanhar demandas.', 'data_sources': [f'{prefix}_demanda'], 'components': ['DemandForm', 'DemandGallery', 'PriorityBadge', 'SubmitForApprovalButton']},
        {'name': 'scrRequisitos', 'title': 'Requisitos', 'purpose': 'Detalhar requisitos, regras e criterios de aceite.', 'data_sources': [f'{prefix}_requisito', f'{prefix}_demanda'], 'components': ['RequirementForm', 'AcceptanceCriteriaEditor', 'TraceabilityPanel']},
        {'name': 'scrAprovacoes', 'title': 'Aprovacoes', 'purpose': 'Decidir aprovacao, rejeicao ou devolucao para ajuste.', 'data_sources': [f'{prefix}_aprovacao'], 'components': ['ApprovalQueue', 'DecisionPanel', 'AuditTimeline']},
        {'name': 'scrEvidencias', 'title': 'Evidencias', 'purpose': 'Registrar evidencias de qualidade, operacao e release.', 'data_sources': [f'{prefix}_evidencia', f'{prefix}_release'], 'components': ['EvidenceUpload', 'EvidenceGallery', 'ReleaseLink']},
    ]
    return {
        'app_type': 'canvas',
        'name': f'{solution_name} Canvas App',
        'logical_name': f'{prefix}_{_logical(solution_name)}_canvas',
        'theme': {'primary': '#2563EB', 'accent': '#10B981', 'warning': '#F59E0B', 'danger': '#DC2626'},
        'start_screen': 'scrDashboard',
        'layout': 'responsive_tablet',
        'navigation': [{'label': screen['title'], 'target': screen['name']} for screen in screens],
        'screens': screens,
        'offline': {'enabled': False, 'reason': 'P0 usa Dataverse online e ALM sandbox-first.'},
    }


def _flows(prefix: str) -> list[dict[str, Any]]:
    return [
        {'name': 'ReqSys - Intake de demanda', 'trigger': 'Dataverse: row added on Demandas', 'actions': ['Calcular prioridade', 'Criar aprovacao inicial', 'Notificar Teams'], 'connection_references': ['shared_commondataserviceforapps', 'shared_teams'], 'run_as': 'service_principal_or_owner'},
        {'name': 'ReqSys - Aprovacao de requisito', 'trigger': 'Dataverse: status em_aprovacao on Requisitos', 'actions': ['Start and wait for approval', 'Atualizar requisito', 'Registrar evidencia'], 'connection_references': ['shared_commondataserviceforapps', 'shared_approvals'], 'run_as': 'service_principal_or_owner'},
        {'name': 'ReqSys - Release governance', 'trigger': 'Manual button or scheduled', 'actions': ['Consolidar evidencias', 'Gerar go/no-go', 'Notificar stakeholders'], 'connection_references': ['shared_commondataserviceforapps', 'shared_teams', 'shared_sharepointonline'], 'run_as': 'service_principal_or_owner'},
        {'name': 'ReqSys - Copilot handoff', 'trigger': 'Copilot Studio action', 'actions': ['Criar demanda', 'Vincular contexto', 'Retornar numero da demanda'], 'connection_references': ['shared_commondataserviceforapps'], 'run_as': 'service_principal_or_owner'},
    ]


def _copilot(prefix: str, solution_name: str) -> dict[str, Any]:
    return {
        'name': f'{solution_name} Copilot',
        'target': 'copilot_studio',
        'language': 'pt-BR',
        'instructions': ['Atue como orquestrador low-code do ReqSys.', 'Converta pedidos vagos em demandas estruturadas no Dataverse.', 'Sempre confirme antes de criar aprovacao, release ou acao externa.', 'Explique status, pendencias e proximo passo em linguagem executiva.'],
        'topics': [
            {'name': 'Criar demanda', 'intent': 'Registrar nova solicitacao', 'action': 'ReqSys - Copilot handoff'},
            {'name': 'Consultar status', 'intent': 'Consultar demanda ou requisito', 'data_source': f'{prefix}_demanda'},
            {'name': 'Preparar aprovacao', 'intent': 'Gerar resumo para aprovador', 'data_source': f'{prefix}_aprovacao'},
            {'name': 'Resumo de release', 'intent': 'Gerar go/no-go executivo', 'data_source': f'{prefix}_release'},
        ],
        'knowledge_sources': ['Dataverse ReqSysLowCode', 'SharePoint evidencias governadas'],
    }


def _security_roles(prefix: str) -> list[dict[str, Any]]:
    tables = [f'{prefix}_{name}' for name in ['demanda', 'requisito', 'aprovacao', 'evidencia', 'release']]
    return [
        {'name': 'ReqSys Solicitante', 'description': 'Cria demandas e consulta itens proprios.', 'privileges': {table: ['read_own', 'create_own', 'append_own'] for table in tables[:2]}},
        {'name': 'ReqSys Aprovador', 'description': 'Avalia demandas e requisitos em aprovacao.', 'privileges': {table: ['read_org', 'write_assigned', 'append_org'] for table in tables[:3]}},
        {'name': 'ReqSys Administrador Low-Code', 'description': 'Administra a solution low-code e suas configuracoes.', 'privileges': {table: ['create_org', 'read_org', 'write_org', 'delete_org', 'append_org'] for table in tables}},
        {'name': 'ReqSys Auditor', 'description': 'Consulta evidencias, aprovacoes e releases sem alterar dados.', 'privileges': {table: ['read_org'] for table in tables}},
    ]


def _alm_package(request: LowCodeSolutionGenerateRequest, prefix: str) -> dict[str, Any]:
    return {
        'package_name': PACKAGE_NAME,
        'solution_name': request.solution_name,
        'publisher_prefix': prefix,
        'target_repository': settings.github_alm_repo or 'ericson-j-santos/reqsys-powerplatform-alm',
        'target_environment': request.target_environment,
        'mode': 'dry_run_manifest' if request.dry_run else 'pipeline_dispatch_requested',
        'expected_pipeline': 'lowcode-solution-factory-p0.yml',
        'pac_cli_steps': ['pac auth create', f'pac solution init --publisher-prefix {prefix} --publisher-name ReqSys', 'pac solution add-reference', 'pac solution pack', 'pac solution import'],
        'connection_references': ['shared_commondataserviceforapps', 'shared_teams', 'shared_approvals', 'shared_sharepointonline'],
        'requires_approval': True,
        'secrets_required': ['POWERPLATFORM_APP_ID', 'POWERPLATFORM_CLIENT_SECRET', 'POWERPLATFORM_TENANT_ID', 'DEV_ENVIRONMENT_URL ou TARGET_ENVIRONMENT_URL'],
    }


def _canvas_markdown(solution: dict[str, Any]) -> str:
    app = solution['apps']['canvas_app'] or {'name': 'Canvas App nao incluido', 'start_screen': 'n/a', 'layout': 'n/a', 'screens': []}
    screens = '\n'.join(f"| {screen['title']} | {screen['purpose']} | {', '.join(screen['components'])} |" for screen in app['screens']) or '| n/a | Modulo Power Apps nao incluido | n/a |'
    flows = '\n'.join(f"| {flow['name']} | {flow['trigger']} | {', '.join(flow['actions'])} |" for flow in solution['flows']) or '| n/a | Modulo Power Automate nao incluido | n/a |'
    tables = '\n'.join(f"| {table['display_name']} | `{table['logical_name']}` | {len(table['columns'])} |" for table in solution['dataverse']['tables']) or '| n/a | Modulo Dataverse nao incluido | 0 |'
    copilot = solution['copilot'] or {'name': 'Copilot nao incluido', 'topics': []}
    topics = ', '.join(topic['name'] for topic in copilot['topics']) or 'n/a'
    roles = ', '.join(role['name'] for role in solution['security_roles']) or 'Security roles nao incluidas'
    return f"""# {solution['display_name']} - Canvas da Solution

## Visao geral

Solution: `{solution['solution_name']}`{_MD_BR}
Ambiente alvo: `{solution['target_environment']}`{_MD_BR}
Modo: `{solution['governance']['mode']}`{_MD_BR}
Status: `{solution['status']}`

## Canvas App

App: `{app['name']}`{_MD_BR}
Tela inicial: `{app['start_screen']}`{_MD_BR}
Layout: `{app['layout']}`

| Tela | Objetivo | Componentes |
| --- | --- | --- |
{screens}

## Dataverse

| Tabela | Logical name | Colunas |
| --- | --- | ---: |
{tables}

## Power Automate

| Flow | Trigger | Acoes |
| --- | --- | --- |
{flows}

## Copilot Studio

Agente: `{copilot['name']}`{_MD_BR}
Topicos: {topics}

## Security roles

{roles}
"""


def _zip_base64(files: list[dict[str, str]]) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            archive.writestr(f"{PACKAGE_NAME}/{file['path']}", file['content'])
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def montar_arquivos_solution(solution: dict[str, Any]) -> list[dict[str, str]]:
    files = [
        {'path': 'manifest.json', 'content': json.dumps(solution, ensure_ascii=False, indent=2)},
        {'path': 'dataverse/schema.json', 'content': json.dumps(solution['dataverse'], ensure_ascii=False, indent=2)},
        {'path': 'powerapps/canvas-app.json', 'content': json.dumps(solution['apps']['canvas_app'], ensure_ascii=False, indent=2)},
        {'path': 'powerautomate/flows.json', 'content': json.dumps(solution['flows'], ensure_ascii=False, indent=2)},
        {'path': 'copilot/copilot-studio.json', 'content': json.dumps(solution['copilot'], ensure_ascii=False, indent=2)},
        {'path': 'security/security-roles.json', 'content': json.dumps(solution['security_roles'], ensure_ascii=False, indent=2)},
        {'path': 'alm/package-plan.json', 'content': json.dumps(solution['alm_package'], ensure_ascii=False, indent=2)},
        {'path': 'CANVAS.md', 'content': solution['canvas_markdown']},
    ]
    return sorted(files, key=lambda item: PurePosixPath(item['path']).as_posix())


def gerar_lowcode_solution(request: LowCodeSolutionGenerateRequest) -> dict[str, Any]:
    if request.profile == 'teams_notification_v2':
        solution = gerar_teams_notification_solution(
            target_environment=request.target_environment,
            dry_run=request.dry_run,
        )
        solution['profile'] = request.profile
        solution['factory_version'] = FACTORY_VERSION
        return solution

    prefix = _logical(request.owner_prefix)[:20]
    modules = set(request.modules)
    solution: dict[str, Any] = {
        'schema_version': FACTORY_VERSION,
        'capability': 'LowCode Solution Factory P0',
        'profile': request.profile,
        'status': 'planned' if request.dry_run else 'ready_for_pipeline',
        'correlation_id': str(uuid.uuid4()),
        'generated_at': _utc_now(),
        'solution_name': request.solution_name,
        'display_name': request.display_name,
        'description': request.description,
        'target_environment': request.target_environment,
        'modules': request.modules,
        'publisher': {'name': 'ReqSys', 'prefix': prefix},
        'governance': {
            'mode': 'dry_run_blueprint' if request.dry_run else 'alm_pipeline_requested',
            'sandbox_first': True,
            'requires_human_or_pipeline_approval': True,
            'no_custom_reqsys_api_required': True,
            'external_write_guardrails': ['nao importar em producao sem aprovacao', 'nao gravar client secrets no ReqSys', 'usar connection references por ambiente', 'gerar evidencias e plano de rollback'],
        },
        'dataverse': _dataverse_schema(prefix) if 'dataverse' in modules else {'tables': [], 'relationships': [], 'choices': {}},
        'apps': {'canvas_app': _canvas_app(prefix, request.solution_name) if 'powerapps' in modules else {}},
        'flows': _flows(prefix) if 'powerautomate' in modules else [],
        'copilot': _copilot(prefix, request.solution_name) if 'copilot' in modules else {},
        'security_roles': _security_roles(prefix) if 'security' in modules else [],
        'alm_package': _alm_package(request, prefix) if request.include_alm_package else {},
    }
    solution['canvas_markdown'] = _canvas_markdown(solution) if request.include_canvas_markdown else ''
    files = montar_arquivos_solution(solution)
    solution['package'] = {
        'package_name': PACKAGE_NAME,
        'zip_filename': f'{PACKAGE_NAME}.zip',
        'files': [{'path': file['path'], 'size': len(file['content'])} for file in files],
        'zip_base64': _zip_base64(files),
    }
    return solution
