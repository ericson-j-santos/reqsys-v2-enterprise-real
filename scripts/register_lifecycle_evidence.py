#!/usr/bin/env python3
"""Registra evidência externa no ciclo de vida de um requisito ReqSys.

Uso típico em CI/CD:

python scripts/register_lifecycle_evidence.py \
  --base-url https://reqsys-api-dev.fly.dev \
  --requirement-code REQ-123456789 \
  --type pr \
  --repo owner/repo \
  --reference 1512 \
  --url https://github.com/owner/repo/pull/1512

O token é lido de REQSYS_LIFECYCLE_SERVICE_TOKEN por padrão. Nunca é impresso.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 20
DEFAULT_ATTEMPTS = 3


def _post_json(url: str, token: str, payload: dict[str, Any], correlation_id: str, timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Service-Token': token,
            'X-Correlation-Id': correlation_id,
            'User-Agent': 'reqsys-lifecycle-evidence/1.0',
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        raw = response.read().decode('utf-8')
        return json.loads(raw) if raw else {}


def register(
    *,
    base_url: str,
    token: str,
    requirement_code: str,
    evidence_type: str,
    repo: str,
    reference: str,
    evidence_url: str | None,
    title: str | None,
    environment: str | None,
    provider: str,
    correlation_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = DEFAULT_ATTEMPTS,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/v1/requisitos/lifecycle/codigo/{requirement_code}/evidencias"
    payload = {
        'provedor': provider,
        'tipo': evidence_type,
        'repo': repo,
        'referencia': reference,
        'url': evidence_url,
        'titulo': title,
        'ambiente': environment,
    }

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _post_json(endpoint, token, payload, correlation_id, timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            if 400 <= exc.code < 500:
                raise RuntimeError(f'ReqSys rejeitou a evidência: HTTP {exc.code}: {detail[:500]}') from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc

        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))

    raise RuntimeError(f'Falha ao registrar evidência após {attempts} tentativas: {last_error}')


def _write_output(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Registra evidência do ciclo de vida no ReqSys')
    parser.add_argument('--base-url', default=os.getenv('REQSYS_API_BASE_URL', ''))
    parser.add_argument('--token', default=os.getenv('REQSYS_LIFECYCLE_SERVICE_TOKEN', ''))
    parser.add_argument('--requirement-code', required=True)
    parser.add_argument('--type', required=True, choices=['issue', 'branch', 'pr', 'commit', 'deploy'])
    parser.add_argument('--provider', default='github')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--url')
    parser.add_argument('--title')
    parser.add_argument('--environment', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--correlation-id', default=os.getenv('CORRELATION_ID', 'lifecycle-evidence-cli'))
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--attempts', type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument('--output')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.type == 'deploy' and not args.environment:
        parser.error('--environment é obrigatório quando --type=deploy')
    if args.type != 'deploy' and args.environment:
        parser.error('--environment só é permitido quando --type=deploy')
    if not args.base_url:
        parser.error('--base-url ou REQSYS_API_BASE_URL é obrigatório')
    if not args.token and not args.dry_run:
        parser.error('--token ou REQSYS_LIFECYCLE_SERVICE_TOKEN é obrigatório')

    preview = {
        'requirement_code': args.requirement_code,
        'type': args.type,
        'provider': 'deployment' if args.type == 'deploy' else args.provider,
        'repo': args.repo,
        'reference': args.reference,
        'url': args.url,
        'title': args.title,
        'environment': args.environment,
        'correlation_id': args.correlation_id,
        'dry_run': args.dry_run,
    }

    if args.dry_run:
        _write_output(args.output, preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    try:
        response = register(
            base_url=args.base_url,
            token=args.token,
            requirement_code=args.requirement_code,
            evidence_type=args.type,
            repo=args.repo,
            reference=args.reference,
            evidence_url=args.url,
            title=args.title,
            environment=args.environment,
            provider=args.provider,
            correlation_id=args.correlation_id,
            timeout=max(1, args.timeout),
            attempts=max(1, args.attempts),
        )
    except RuntimeError as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1

    _write_output(args.output, response)
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
