#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTION_PATH = ('Scope_TRY', 'Condição_')
ACTION_NAME = 'Postar_cartão_em_um_chat_ou_canal'
COMPOSE_CARD_ACTION_NAME = 'Compose_AdaptiveCard'


def _request_json(url: str, *, method: str = 'GET', headers: dict[str, str] | None = None, data: dict[str, Any] | None = None) -> dict:
    body = None
    request_headers = {'Accept': 'application/json', **(headers or {})}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw.decode('utf-8')) if raw else {}


def acquire_token(*, tenant_id: str, client_id: str, client_secret: str, environment_url: str) -> str:
    token_url = f'https://login.microsoftonline.com/{urllib.parse.quote(tenant_id)}/oauth2/v2.0/token'
    payload = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': f"{environment_url.rstrip('/')}/.default",
    }).encode('utf-8')
    request = urllib.request.Request(
        token_url,
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
    token = result.get('access_token')
    if not token:
        raise ValueError('Microsoft identity platform não retornou access_token.')
    return token


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def find_workflow(*, environment_url: str, token: str, flow_name: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({
        '$select': 'workflowid,name,clientdata',
        '$filter': f"name eq '{_escape_odata(flow_name)}' and category eq 5",
        '$top': '2',
    })
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows?{query}"
    result = _request_json(url, headers={'Authorization': f'Bearer {token}'})
    rows = result.get('value', [])
    if len(rows) != 1:
        raise ValueError(f'Esperado exatamente um cloud flow {flow_name!r}; encontrados: {len(rows)}.')
    return rows[0]


def adaptive_card_body(*, minimum_version: str = '1.2') -> dict[str, Any]:
    """Card real enviado pelo robo_envia_teamsv2, expresso com as referências
    de ação que já existem no flow (Analisar_JSON/Compose_StampDate/
    Compose_CorrelationId_Final) em vez do trigger genérico — este flow já
    faz o parsing antes de chegar na ação de post."""
    return {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': minimum_version,
        'msteams': {'width': 'Full'},
        'body': [
            {
                'type': 'Container',
                'style': 'emphasis',
                'bleed': True,
                'items': [
                    {
                        'type': 'ColumnSet',
                        'columns': [
                            {
                                'type': 'Column',
                                'width': 'stretch',
                                'items': [
                                    {
                                        'type': 'TextBlock',
                                        'text': "@{body('Analisar_JSON')?['title']}",
                                        'weight': 'Bolder',
                                        'size': 'Large',
                                        'wrap': True,
                                    },
                                    {
                                        'type': 'TextBlock',
                                        'text': "@{body('Analisar_JSON')?['content']}",
                                        'spacing': 'Small',
                                        'isSubtle': True,
                                        'wrap': True,
                                        'maxLines': 3,
                                    },
                                ],
                            },
                            {
                                'type': 'Column',
                                'width': 'auto',
                                'verticalContentAlignment': 'Center',
                                'items': [
                                    {
                                        'type': 'TextBlock',
                                        'text': '✓',
                                        'weight': 'Bolder',
                                        'size': 'ExtraLarge',
                                        'color': 'Good',
                                        'horizontalAlignment': 'Right',
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                'type': 'FactSet',
                'spacing': 'Medium',
                'facts': [
                    {'title': 'Assinatura', 'value': "@{body('Analisar_JSON')?['signature']}"},
                    {'title': 'Data', 'value': "@{outputs('Compose_StampDate')}"},
                    {'title': 'Correlation ID', 'value': "@{outputs('Compose_CorrelationId_Final')}"},
                ],
            },
            {
                'type': 'TextBlock',
                'text': 'Entrega automatizada pelo ReqSys',
                'spacing': 'Medium',
                'isSubtle': True,
                'size': 'Small',
                'wrap': True,
            },
        ],
    }


def build_message_envelope() -> dict[str, Any]:
    return {
        'type': 'message',
        'attachments': [
            {
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': adaptive_card_body(),
            }
        ],
    }


def _navigate_actions(definition: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    node = definition
    for step in path:
        node = node['actions'][step]
    return node


def apply_card_change(clientdata: dict[str, Any]) -> dict[str, Any]:
    """Retorna uma cópia de clientdata com a ação de post trocada para enviar
    o Adaptive Card customizado, mantendo runAfter/operationMetadataId
    intactos para não corromper o grafo de dependências do flow."""
    updated = copy.deepcopy(clientdata)
    definition = updated['properties']['definition']
    scope = _navigate_actions(definition, ACTION_PATH)
    action = scope['actions'][ACTION_NAME]

    if action['inputs']['host']['operationId'] != 'PostCardToConversation':
        raise ValueError('Ação alvo não usa mais PostCardToConversation; abortando para não editar a coisa errada.')

    envelope = build_message_envelope()
    action['inputs']['parameters']['body/messageBody'] = json.dumps(envelope, ensure_ascii=False)

    return updated


def diff_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_action = _navigate_actions(before['properties']['definition'], ACTION_PATH)['actions'][ACTION_NAME]
    after_action = _navigate_actions(after['properties']['definition'], ACTION_PATH)['actions'][ACTION_NAME]
    return {
        'action': ACTION_NAME,
        'operationId': after_action['inputs']['host']['operationId'],
        'before_message_body': before_action['inputs']['parameters']['body/messageBody'],
        'after_message_body': after_action['inputs']['parameters']['body/messageBody'],
    }


def update_workflow_clientdata(*, environment_url: str, token: str, workflow_id: str, clientdata: dict[str, Any]) -> None:
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows({workflow_id})"
    _request_json(
        url,
        method='PATCH',
        headers={'Authorization': f'Bearer {token}', 'If-Match': '*'},
        data={'clientdata': json.dumps(clientdata, ensure_ascii=False)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Troca o post de cartão do robo_envia_teamsv2 para um Adaptive Card customizado.')
    parser.add_argument('--environment-url', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--flow-name', default='robo_envia_teamsv2')
    parser.add_argument('--apply', action='store_true', help='Sem esta flag, roda em modo dry-run (só mostra o diff, não grava nada).')
    parser.add_argument('--confirm', default='', help='Deve ser exatamente UPDATE-REQSYS-TEAMSV2-CARD quando --apply é usado.')
    parser.add_argument('--backup-dir', default='artifacts/teams-v2-card-update')
    parser.add_argument('--output')
    args = parser.parse_args()

    if args.apply and args.confirm != 'UPDATE-REQSYS-TEAMSV2-CARD':
        print(json.dumps({'status': 'blocked', 'error': 'Confirmação ausente ou incorreta para --apply.'}, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        token = acquire_token(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            environment_url=args.environment_url,
        )
        workflow = find_workflow(environment_url=args.environment_url, token=token, flow_name=args.flow_name)
        before = json.loads(workflow['clientdata'])
        after = apply_card_change(before)
        summary = diff_summary(before, after)

        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_path = backup_dir / f"{args.flow_name}-clientdata-before-{timestamp}.json"
        backup_path.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')

        result: dict[str, Any] = {
            'status': 'planned',
            'workflow_id': workflow['workflowid'],
            'flow_name': workflow['name'],
            'backup_path': str(backup_path),
            'diff': summary,
        }

        if args.apply:
            update_workflow_clientdata(
                environment_url=args.environment_url,
                token=token,
                workflow_id=workflow['workflowid'],
                clientdata=after,
            )
            result['status'] = 'applied'

        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
