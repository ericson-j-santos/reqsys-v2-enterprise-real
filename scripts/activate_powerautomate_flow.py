#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class FlowState:
    workflow_id: str
    name: str
    statecode: int
    statuscode: int


def _request_json(url: str, *, method: str = 'GET', headers: dict[str, str] | None = None, data: dict[str, str] | dict[str, int] | None = None) -> dict:
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


def find_flow(*, environment_url: str, token: str, flow_name: str) -> FlowState:
    query = urllib.parse.urlencode({
        '$select': 'workflowid,name,statecode,statuscode',
        '$filter': f"name eq '{_escape_odata(flow_name)}' and category eq 5",
        '$top': '2',
    })
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows?{query}"
    result = _request_json(url, headers={'Authorization': f'Bearer {token}'})
    rows = result.get('value', [])
    if len(rows) != 1:
        raise ValueError(f'Esperado exatamente um cloud flow {flow_name!r}; encontrados: {len(rows)}.')
    row = rows[0]
    return FlowState(
        workflow_id=row['workflowid'],
        name=row['name'],
        statecode=int(row['statecode']),
        statuscode=int(row['statuscode']),
    )


def activate_flow(*, environment_url: str, token: str, flow: FlowState) -> FlowState:
    if flow.statecode == 1:
        return flow
    url = f"{environment_url.rstrip('/')}/api/data/v9.2/workflows({flow.workflow_id})"
    _request_json(
        url,
        method='PATCH',
        headers={'Authorization': f'Bearer {token}', 'If-Match': '*'},
        data={'statecode': 1, 'statuscode': 2},
    )
    return find_flow(environment_url=environment_url, token=token, flow_name=flow.name)


def main() -> int:
    parser = argparse.ArgumentParser(description='Publica/ativa um cloud flow no Power Platform DEV.')
    parser.add_argument('--environment-url', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--flow-name', default='robo_envia_teamsv2')
    parser.add_argument('--output')
    args = parser.parse_args()

    try:
        token = acquire_token(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            environment_url=args.environment_url,
        )
        before = find_flow(environment_url=args.environment_url, token=token, flow_name=args.flow_name)
        after = activate_flow(environment_url=args.environment_url, token=token, flow=before)
        if after.statecode != 1:
            raise ValueError(f'Flow permaneceu inativo após a operação: statecode={after.statecode}.')
        result = {
            'status': 'active',
            'flow_name': after.name,
            'workflow_id': after.workflow_id,
            'statecode_before': before.statecode,
            'statuscode_before': before.statuscode,
            'statecode_after': after.statecode,
            'statuscode_after': after.statuscode,
        }
        if args.output:
            from pathlib import Path

            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
