#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTION_PATH = ('Scope_TRY', 'Condição_')
ACTION_NAME = 'Postar_cartão_em_um_chat_ou_canal'
PARSE_JSON_ACTION_NAME = 'Analisar_JSON'
_PLACEHOLDER_RE = re.compile(r'"@\{([^}]*)\}"')
_BACKSLASH = chr(92)
_DOUBLE_QUOTE = chr(34)


def _request_json(
    url: str,
    *,
    method: str = 'GET',
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict:
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
    payload = urllib.parse.urlencode(
        {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': f"{environment_url.rstrip('/')}/.default",
        }
    ).encode('utf-8')
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
    query = urllib.parse.urlencode(
        {
            '$select': 'workflowid,name,clientdata',
            '$filter': f"name eq '{_escape_odata(flow_name)}' and category eq 5",
            '$top': '2',
        }
    )
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows?{query}"
    result = _request_json(url, headers={'Authorization': f'Bearer {token}'})
    rows = result.get('value', [])
    if len(rows) != 1:
        raise ValueError(f'Esperado exatamente um cloud flow {flow_name!r}; encontrados: {len(rows)}.')
    return rows[0]


def _responsive_field(label: str, expression: str, *, separator: bool = False) -> dict[str, Any]:
    """Renderiza rótulo e valor empilhados para não comprimir o conteúdo no Teams mobile."""
    return {
        'type': 'Container',
        'spacing': 'Small',
        'separator': separator,
        'items': [
            {
                'type': 'TextBlock',
                'text': label,
                'weight': 'Bolder',
                'size': 'Small',
                'isSubtle': True,
                'wrap': True,
            },
            {
                'type': 'TextBlock',
                'text': expression,
                'spacing': 'None',
                'wrap': True,
            },
        ],
    }


def adaptive_card_body(*, minimum_version: str = '1.2') -> dict[str, Any]:
    """Card genérico do robo_envia_teamsv2 com largura total e campos empilhados.

    O flow repassa o ``adaptiveCard`` produzido pelo chamador quando presente.
    Este template é o fallback visual para integrações legadas que enviam somente
    title/content/signature/stampDate/correlationId.
    """
    return {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': minimum_version,
        'msteams': {'width': 'Full'},
        'fallbackText': "@{body('Analisar_JSON')?['title']}",
        'body': [
            {
                'type': 'Container',
                'style': 'emphasis',
                'bleed': True,
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
                        'maxLines': 6,
                    },
                ],
            },
            _responsive_field(
                'Assinatura',
                "@{body('Analisar_JSON')?['signature']}",
                separator=True,
            ),
            _responsive_field('Data', "@{outputs('Compose_StampDate')}"),
            _responsive_field('Correlation ID', "@{outputs('Compose_CorrelationId_Final')}"),
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


def _navigate_actions(definition: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    node = definition
    for step in path:
        node = node['actions'][step]
    return node


def _wdl_string_literal(text: str) -> str:
    """Escapa um literal para uso dentro de uma expressão WDL (aspas simples dobradas)."""
    return "'" + text.replace("'", "''") + "'"


def _wdl_escape_json_string(expr: str) -> str:
    """Escapa valor dinâmico para inserção segura em uma string JSON WDL."""
    escaped = expr
    escaped = (
        f"replace({escaped}, {_wdl_string_literal(_BACKSLASH)}, "
        f"{_wdl_string_literal(_BACKSLASH * 2)})"
    )
    escaped = (
        f"replace({escaped}, {_wdl_string_literal(_DOUBLE_QUOTE)}, "
        f"{_wdl_string_literal(_BACKSLASH + _DOUBLE_QUOTE)})"
    )
    escaped = f"replace({escaped}, decodeUriComponent('%0D'), {_wdl_string_literal('')})"
    escaped = (
        f"replace({escaped}, decodeUriComponent('%0A'), "
        f"{_wdl_string_literal(_BACKSLASH + 'n')})"
    )
    return escaped


def _json_to_concat_expression(value: dict[str, Any]) -> str:
    """Converte um dict com folhas ``@{expressao}`` em concat() WDL seguro."""
    text = json.dumps(value, ensure_ascii=False)
    parts: list[str] = []
    last_end = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        literal_before = text[last_end : match.start() + 1]
        if literal_before:
            parts.append(_wdl_string_literal(literal_before))
        parts.append(_wdl_escape_json_string(match.group(1)))
        last_end = match.end() - 1
    tail = text[last_end:]
    if tail:
        parts.append(_wdl_string_literal(tail))
    if not parts:
        parts.append(_wdl_string_literal(text))
    return f"concat({', '.join(parts)})"


def build_message_body_expression() -> str:
    """Usa o cartão do chamador; aplica o template responsivo apenas como fallback."""
    fallback_expr = _json_to_concat_expression(adaptive_card_body())
    return (
        "@{if(empty(body('Analisar_JSON')?['adaptiveCard']), "
        f"{fallback_expr}, body('Analisar_JSON')?['adaptiveCard'])}}"
    )


def apply_card_change(clientdata: dict[str, Any]) -> dict[str, Any]:
    """Atualiza o post do flow sem alterar dependências ou metadados da ação."""
    updated = copy.deepcopy(clientdata)
    definition = updated['properties']['definition']
    scope = _navigate_actions(definition, ACTION_PATH)
    action = scope['actions'][ACTION_NAME]

    if action['inputs']['host']['operationId'] != 'PostCardToConversation':
        raise ValueError(
            'Ação alvo não usa mais PostCardToConversation; abortando para não editar a coisa errada.'
        )

    action['inputs']['parameters']['body/messageBody'] = build_message_body_expression()

    parse_json = _navigate_actions(definition, ('Scope_TRY',))['actions'][PARSE_JSON_ACTION_NAME]
    properties = parse_json['inputs']['schema']['properties']
    properties.setdefault('adaptiveCard', {'type': 'object'})
    properties.setdefault('adaptiveCardJson', {'type': 'string'})
    properties.setdefault('renderMode', {'type': 'string'})
    properties.setdefault('eventType', {'type': 'string'})
    properties.setdefault('deduplicationKey', {'type': 'string'})
    properties.setdefault('suppressFallbackMessage', {'type': 'boolean'})

    return updated


def diff_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_action = _navigate_actions(before['properties']['definition'], ACTION_PATH)['actions'][
        ACTION_NAME
    ]
    after_action = _navigate_actions(after['properties']['definition'], ACTION_PATH)['actions'][
        ACTION_NAME
    ]
    return {
        'action': ACTION_NAME,
        'operationId': after_action['inputs']['host']['operationId'],
        'before_message_body': before_action['inputs']['parameters']['body/messageBody'],
        'after_message_body': after_action['inputs']['parameters']['body/messageBody'],
        'layout': 'full-width-stacked-mobile',
    }


def update_workflow_clientdata(
    *,
    environment_url: str,
    token: str,
    workflow_id: str,
    clientdata: dict[str, Any],
) -> None:
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows({workflow_id})"
    _request_json(
        url,
        method='PATCH',
        headers={'Authorization': f'Bearer {token}', 'If-Match': '*'},
        data={'clientdata': json.dumps(clientdata, ensure_ascii=False)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Atualiza o robo_envia_teamsv2 para Adaptive Card responsivo.'
    )
    parser.add_argument('--environment-url', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--flow-name', default='robo_envia_teamsv2')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Sem esta flag, roda em dry-run e somente mostra o diff.',
    )
    parser.add_argument(
        '--confirm',
        default='',
        help='Deve ser exatamente UPDATE-REQSYS-TEAMSV2-CARD quando --apply é usado.',
    )
    parser.add_argument('--backup-dir', default='artifacts/teams-v2-card-update')
    parser.add_argument('--output')
    args = parser.parse_args()

    if args.apply and args.confirm != 'UPDATE-REQSYS-TEAMSV2-CARD':
        print(
            json.dumps(
                {'status': 'blocked', 'error': 'Confirmação ausente ou incorreta para --apply.'},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    try:
        token = acquire_token(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            environment_url=args.environment_url,
        )
        workflow = find_workflow(
            environment_url=args.environment_url,
            token=token,
            flow_name=args.flow_name,
        )
        before = json.loads(workflow['clientdata'])
        after = apply_card_change(before)
        summary = diff_summary(before, after)

        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_path = backup_dir / f"{args.flow_name}-clientdata-before-{timestamp}.json"
        backup_path.write_text(
            json.dumps(before, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

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
            path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(
            json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
