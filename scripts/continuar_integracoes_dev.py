#!/usr/bin/env python3
"""Preflight DEV pelo locator canônico; reprocessamento Planner opcional.

Não cria identidade, segredo ou runtime substituto. Execução com efeito externo:
  python scripts/continuar_integracoes_dev.py --expected-sha <SHA> --reprocessar-planner
Token: PLANNER_PUBLISH_SERVICE_TOKEN no contexto/cofre de execução.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def resolver_dev() -> str:
    # O resolver Node valida assinatura, prazo, ambiente e domínio. Evitar que
    # ele publique outputs GitHub antes de o preflight concluir.
    env = dict(os.environ)
    env.pop('GITHUB_OUTPUT', None)
    # Node recente suporta os proxies do ambiente também para fetch.
    env.setdefault('NODE_USE_ENV_PROXY', '1')
    result = subprocess.run(
        ['node', str(ROOT / 'scripts/resolve_pc24x7_dev_locator.mjs')],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise RuntimeError('locator_dev_indisponivel')
    payload = json.loads(result.stdout)
    if payload.get('signature_verified') is not True or payload.get('environment') != 'dev':
        raise RuntimeError('locator_dev_invalido')
    return payload['selected_url'].rstrip('/') + '/api'


def ler_runtime(base_url: str, path: str) -> dict:
    request = Request(base_url + path, headers={'Accept': 'application/json'})
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
        if response.status != 200 or not isinstance(payload, dict) or payload.get('success') is False:
            raise RuntimeError('runtime_dev_indisponivel')
        return payload


def preflight(expected_sha: str = '') -> dict:
    token = bool(os.environ.get('PLANNER_PUBLISH_SERVICE_TOKEN', '').strip())
    report = {
        'schema_version': '1.0.0', 'environment': 'dev',
        'status': 'BLOCKED_EXTERNAL', 'planner_service_token_configured': token,
        'planner_reprocess_executed': False, 'hml_prod_touched': False,
        'secret_values_exposed': False, 'blockers': [],
        'redmine_live_validation': 'pending', 'expected_sha_verified': False,
    }
    if not token:
        report['blockers'].append('PLANNER_PUBLISH_SERVICE_TOKEN_ausente_no_contexto')
    try:
        base_url = resolver_dev()
        report['api_base_url'] = base_url
        health = ler_runtime(base_url, '/health')
        health_data = health.get('data', health)
        if not isinstance(health_data, dict) or health_data.get('status') not in ('ok', 'healthy'):
            raise RuntimeError('runtime_health_nao_confirmado')
        build = ler_runtime(base_url, '/runtime/build-info')
        data = build.get('data', build)
        if not isinstance(data, dict):
            raise RuntimeError('runtime_sha_nao_confirmado')
        sha = data.get('build_sha') or data.get('commit_sha')
        if not isinstance(sha, str) or len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha.lower()):
            raise RuntimeError('runtime_sha_nao_confirmado')
        report['runtime_sha'] = sha
        report['runtime_health'] = 'passed'
        if expected_sha:
            report['expected_sha'] = expected_sha
            if sha != expected_sha:
                raise RuntimeError('runtime_sha_divergente')
            report['expected_sha_verified'] = True
    except HTTPError as exc:
        report['blockers'].append(f'runtime_dev_http_{exc.code}')
    except RuntimeError as exc:
        # Só códigos locais conhecidos; nunca mensagem de erro remota/segredo.
        report['blockers'].append(str(exc))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        report['blockers'].append('runtime_dev_preflight_falhou')
    if not report['blockers']:
        report['status'] = 'ready_for_planner_reprocess'
    return report


def executar_planner(report: dict) -> None:
    if report['status'] != 'ready_for_planner_reprocess' or not report['expected_sha_verified']:
        return
    # Importa a implementação existente, sem fila/autenticação concorrentes.
    import planner_publish_reprocess_pendentes as planner

    previous = sys.argv
    sys.argv = [
        'planner_publish_reprocess_pendentes.py', '--base-url', report['api_base_url'],
        '--service-token', os.environ['PLANNER_PUBLISH_SERVICE_TOKEN'],
        '--lote-max', '10', '--strict',
    ]
    try:
        planner.main()
        report['planner_reprocess_executed'] = True
        report['status'] = 'planner_reprocess_completed'
    except (SystemExit, Exception):
        report['status'] = 'planner_reprocess_failed'
        report['blockers'].append('planner_reprocess_falhou')
    finally:
        sys.argv = previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reprocessar-planner', action='store_true')
    parser.add_argument('--expected-sha', default='', help='SHA publicado exigido antes de qualquer reprocessamento.')
    parser.add_argument('--evidence-file', default='artifacts/integracoes-dev/preflight.json')
    args = parser.parse_args()
    report = preflight(args.expected_sha)
    if args.reprocessar_planner:
        if not args.expected_sha:
            report['status'] = 'BLOCKED_EXTERNAL'
            report['blockers'].append('expected_sha_necessario_para_reprocessamento')
        executar_planner(report)
    target = Path(args.evidence_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 2 if report['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
