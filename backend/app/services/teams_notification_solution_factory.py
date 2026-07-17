from __future__ import annotations

import base64
import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

SOLUTION_NAME = 'ReqSysTeamsNotifications'
FLOW_NAME = 'robo_envia_teamsv2'
FLOW_VERSION = '2.0.0.0'
PACKAGE_FILENAME = 'reqsys-teams-notifications-v2.zip'
SCHEMA_VERSION = '1.0.0'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trigger_schema() -> dict[str, Any]:
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'title': 'ReqSys Teams Notification v2',
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 180},
            'content': {'type': 'string', 'maxLength': 12000},
            'signature': {'type': 'string', 'maxLength': 120},
            'stampDate': {'type': 'string', 'format': 'date-time'},
            'correlationId': {'type': 'string', 'format': 'uuid'},
            'renderMode': {'type': 'string', 'enum': ['adaptive-card', 'markdown']},
            'adaptiveCard': {'type': 'object'},
            'adaptiveCardJson': {'type': 'string'},
        },
        'required': ['title', 'content', 'correlationId'],
    }


def _environment_variables() -> list[dict[str, Any]]:
    return [
        {
            'schema_name': 'reqsys_TeamsDestination',
            'display_name': 'ReqSys Teams destination',
            'type': 'string',
            'required': True,
            'default_value': '',
            'secret': False,
        },
        {
            'schema_name': 'reqsys_TeamsPublishMode',
            'display_name': 'ReqSys Teams publish mode',
            'type': 'string',
            'required': True,
            'default_value': 'chat_or_channel',
            'allowed_values': ['chat_or_channel', 'channel', 'group_chat'],
            'secret': False,
        },
        {
            'schema_name': 'reqsys_TeamsFallbackEnabled',
            'display_name': 'ReqSys Teams fallback enabled',
            'type': 'boolean',
            'required': True,
            'default_value': True,
            'secret': False,
        },
        {
            'schema_name': 'reqsys_AdaptiveCardMinimumVersion',
            'display_name': 'ReqSys Adaptive Card minimum version',
            'type': 'string',
            'required': True,
            'default_value': '1.5',
            'secret': False,
        },
        {
            'schema_name': 'reqsys_NotificationApplicationId',
            'display_name': 'ReqSys notification application id',
            'type': 'string',
            'required': True,
            'default_value': SOLUTION_NAME,
            'secret': False,
        },
    ]


def _flow_definition() -> dict[str, Any]:
    return {
        'name': FLOW_NAME,
        'display_name': 'ReqSys - Enviar notificacao Teams v2',
        'version': FLOW_VERSION,
        'state': 'off_after_import',
        'trigger': {
            'type': 'Request',
            'kind': 'Http',
            'method': 'POST',
            'schema_file': 'powerautomate/http-trigger-schema.json',
            'authentication': 'platform_managed',
        },
        'connection_references': [
            {
                'logical_name': 'reqsys_sharedteams',
                'connector': 'shared_teams',
                'required': True,
            }
        ],
        'environment_variables': [item['schema_name'] for item in _environment_variables()],
        'variables': [
            {'name': 'correlationId', 'type': 'string', 'source': "triggerBody()?['correlationId']"},
            {'name': 'renderMode', 'type': 'string', 'default': 'markdown'},
            {'name': 'teamsNotified', 'type': 'boolean', 'default': False},
        ],
        'rendering_rules': [
            {
                'priority': 1,
                'condition': "and(equals(triggerBody()?['renderMode'], 'adaptive-card'), not(empty(triggerBody()?['adaptiveCard'])))",
                'action': 'Post adaptive card in a chat or channel',
                'payload_expression': "triggerBody()?['adaptiveCard']",
                'result_mode': 'adaptive-card',
            },
            {
                'priority': 2,
                'condition': "and(equals(triggerBody()?['renderMode'], 'adaptive-card'), empty(triggerBody()?['adaptiveCard']), not(empty(triggerBody()?['adaptiveCardJson'])))",
                'action': 'Post adaptive card in a chat or channel',
                'payload_expression': "json(triggerBody()?['adaptiveCardJson'])",
                'result_mode': 'adaptive-card-json',
            },
            {
                'priority': 3,
                'condition': "equals(parameters('reqsys_TeamsFallbackEnabled'), true)",
                'action': 'Post message in a chat or channel',
                'payload_expression': "triggerBody()?['content']",
                'result_mode': 'markdown-fallback',
            },
        ],
        'scopes': {
            'main': {
                'retry_policy': {'type': 'exponential', 'count': 3, 'interval': 'PT10S'},
                'timeout': 'PT1M',
                'actions': ['Validate payload', 'Resolve render mode', 'Publish to Teams', 'Return success'],
            },
            'fallback': {
                'run_after': ['main:Failed', 'main:TimedOut'],
                'actions': ['Publish sanitized fallback', 'Return degraded success'],
            },
            'error': {
                'run_after': ['fallback:Failed', 'fallback:TimedOut'],
                'actions': ['Return sanitized error'],
            },
        },
        'success_response': {
            'status_code': 200,
            'body': {
                'ok': True,
                'renderMode': '@variables(renderMode)',
                'teams_notificado': '@variables(teamsNotified)',
                'correlationId': '@variables(correlationId)',
                'flowVersion': FLOW_VERSION,
            },
        },
        'error_response': {
            'status_code': 502,
            'body': {
                'ok': False,
                'errorCode': 'TEAMS_POST_FAILED',
                'message': 'Falha ao publicar notificacao no Teams.',
                'correlationId': '@variables(correlationId)',
                'flowVersion': FLOW_VERSION,
            },
        },
        'idempotency': {
            'key': 'correlationId',
            'strategy': 'reject_or_return_previous_result',
            'persistence': 'environment_specific_store',
            'required_before_production': True,
        },
        'logging': {
            'include': ['correlationId', 'renderMode', 'teams_notificado', 'flowVersion', 'duration_ms'],
            'exclude': ['adaptiveCardJson', 'content', 'tokens', 'webhooks', 'connection_secrets'],
        },
    }


def _migration_plan() -> dict[str, Any]:
    return {
        'source_flow': 'robo_envia_teamsv1',
        'target_flow': FLOW_NAME,
        'steps': [
            'Importar a solution em DEV com o flow inicialmente desligado.',
            'Configurar connection reference e environment variables.',
            'Executar testes de contrato e teste real em Teams desktop e mobile.',
            'Executar v1 e v2 em paralelo durante janela controlada.',
            'Alterar o webhook do gateway ReqSys para v2.',
            'Validar erros, consumo, duplicidades e correlationId.',
            'Desativar v1 somente apos estabilidade e rollback testado.',
        ],
        'rollback': [
            'Reapontar o gateway para o endpoint do robo_envia_teamsv1.',
            'Desligar o robo_envia_teamsv2.',
            'Preservar evidencias e correlationIds da janela de falha.',
        ],
    }


def _files(blueprint: dict[str, Any]) -> list[dict[str, str]]:
    files = {
        'manifest.json': blueprint,
        'powerautomate/flow-definition.json': blueprint['flow'],
        'powerautomate/http-trigger-schema.json': blueprint['trigger_schema'],
        'powerplatform/connection-references.json': blueprint['connection_references'],
        'powerplatform/environment-variables.json': blueprint['environment_variables'],
        'alm/migration-and-rollback.json': blueprint['migration'],
        'tests/contract-cases.json': blueprint['contract_tests'],
    }
    return [
        {'path': path, 'content': json.dumps(content, ensure_ascii=False, indent=2)}
        for path, content in sorted(files.items())
    ]


def _zip_base64(files: list[dict[str, str]]) -> tuple[str, str]:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            archive.writestr(f'{SOLUTION_NAME}/{file["path"]}', file['content'])
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode('ascii'), hashlib.sha256(raw).hexdigest()


def gerar_teams_notification_solution(*, target_environment: str = 'dev', dry_run: bool = True) -> dict[str, Any]:
    correlation_id = str(uuid.uuid4())
    blueprint: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'capability': 'ReqSys Teams Notifications Low-Code Solution',
        'status': 'planned' if dry_run else 'ready_for_materialization',
        'generated_at': _utc_now(),
        'correlation_id': correlation_id,
        'solution': {
            'unique_name': SOLUTION_NAME,
            'display_name': 'ReqSys Teams Notifications',
            'version': FLOW_VERSION,
            'publisher': {'name': 'ReqSys', 'prefix': 'reqsys'},
            'target_environment': target_environment,
        },
        'flow': _flow_definition(),
        'trigger_schema': _trigger_schema(),
        'connection_references': _flow_definition()['connection_references'],
        'environment_variables': _environment_variables(),
        'migration': _migration_plan(),
        'contract_tests': [
            {'id': 'adaptive-card-object', 'expected_mode': 'adaptive-card'},
            {'id': 'adaptive-card-json', 'expected_mode': 'adaptive-card-json'},
            {'id': 'legacy-markdown-fallback', 'expected_mode': 'markdown-fallback'},
            {'id': 'invalid-json-fallback', 'expected_mode': 'markdown-fallback'},
            {'id': 'teams-temporary-failure', 'expected': 'retry_then_success_or_fallback'},
            {'id': 'teams-definitive-failure', 'expected_status': 502},
            {'id': 'duplicate-correlation-id', 'expected': 'no_duplicate_post'},
            {'id': 'mobile-long-content', 'expected': 'wrapped_and_actions_visible'},
            {'id': 'log-sanitization', 'expected': 'no_secret_or_payload_body'},
        ],
        'governance': {
            'sandbox_first': True,
            'requires_approval': True,
            'secrets_embedded': False,
            'activate_after_import': False,
            'minimum_adaptive_card_version': '1.5',
        },
    }
    files = _files(blueprint)
    zip_base64, sha256 = _zip_base64(files)
    blueprint['package'] = {
        'filename': PACKAGE_FILENAME,
        'sha256': sha256,
        'files': [{'path': file['path'], 'size': len(file['content'].encode('utf-8'))} for file in files],
        'zip_base64': zip_base64,
    }
    return blueprint
