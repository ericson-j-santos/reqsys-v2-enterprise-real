#!/usr/bin/env python3
"""Diagnóstico somente-leitura: procura texto estático suspeito (ex.: um
card de teste deixado no Maker Portal) em qualquer lugar da definição do
flow robo_envia_teamsv2, e imprime a árvore de ações dentro de qualquer
Condição encontrada no caminho até a ação de post. Não grava nada."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_NEEDLES = ["482", "Portabilidade Consignado", "Comitê de Priorização", "Comite de Priorizacao"]


def _request_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers={'Accept': 'application/json', **(headers or {})}, method='GET')
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
        token_url, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST',
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
        '$select': 'workflowid,name,clientdata,statecode,modifiedon',
        '$filter': f"name eq '{_escape_odata(flow_name)}' and category eq 5",
        '$top': '5',
    })
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows?{query}"
    result = _request_json(url, headers={'Authorization': f'Bearer {token}'})
    return result.get('value', [])


def find_needles(node: Any, needles: list[str], path: str, hits: list[dict[str, Any]]) -> None:
    if isinstance(node, str):
        for needle in needles:
            if needle in node:
                hits.append({'path': path, 'needle': needle, 'snippet': node[:400]})
        return
    if isinstance(node, dict):
        for key, value in node.items():
            find_needles(value, needles, f'{path}.{key}', hits)
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            find_needles(value, needles, f'{path}[{index}]', hits)


def summarize_actions(actions: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for name, action in actions.items():
        entry: dict[str, Any] = {'type': action.get('type')}
        op_id = (action.get('inputs') or {}).get('host', {}).get('operationId') if isinstance(action.get('inputs'), dict) else None
        if op_id:
            entry['operationId'] = op_id
        if action.get('type') == 'If':
            entry['expression'] = action.get('expression')
            entry['true_actions'] = sorted((action.get('actions') or {}).keys())
            entry['else_actions'] = sorted((action.get('else', {}).get('actions') or {}).keys())
        elif 'actions' in action:
            entry['nested_actions'] = sorted(action['actions'].keys())
        summary[name] = entry
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspeciona (somente leitura) a definição do robo_envia_teamsv2.')
    parser.add_argument('--environment-url', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--flow-name', default='robo_envia_teamsv2')
    parser.add_argument('--needle', action='append', default=[])
    args = parser.parse_args()

    needles = args.needle or DEFAULT_NEEDLES

    try:
        token = acquire_token(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            environment_url=args.environment_url,
        )
        rows = find_workflow(environment_url=args.environment_url, token=token, flow_name=args.flow_name)
        result: dict[str, Any] = {'flow_name': args.flow_name, 'matches_found': len(rows), 'workflows': []}
        for row in rows:
            clientdata = json.loads(row['clientdata'])
            definition = clientdata['properties']['definition']
            hits: list[dict[str, Any]] = []
            find_needles(definition, needles, 'definition', hits)
            scope_try = (definition.get('actions') or {}).get('Scope_TRY', {})
            entry = {
                'workflowid': row['workflowid'],
                'statecode': row.get('statecode'),
                'modifiedon': row.get('modifiedon'),
                'needle_hits': hits,
                'top_level_actions': summarize_actions(definition.get('actions') or {}),
                'scope_try_actions': summarize_actions(scope_try.get('actions') or {}),
            }
            result['workflows'].append(entry)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
