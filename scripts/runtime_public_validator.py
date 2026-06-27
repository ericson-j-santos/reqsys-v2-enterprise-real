#!/usr/bin/env python3
"""Validador consolidado da Trilha A — Runtime Público.

Orquestra validação local Fly (config + Docker), probe HTTP opcional e
fallback progressivo para artifacts em cache, sem secrets e sem deploy.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FALLBACK_CANDIDATES = (
    Path('audit/runtime/public-runtime-validation.json'),
    Path('artifacts/runtime/public-runtime-validation.json'),
    Path('public-runtime-validation.json'),
)

TRACKS = (
    'fly_config',
    'docker_smoke',
    'public_probe',
    'fallback_cache',
)


def _run_json_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    stdout = completed.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
            payload['exit_code'] = completed.returncode
            return payload
        except json.JSONDecodeError:
            pass
    return {
        'ok': completed.returncode == 0,
        'exit_code': completed.returncode,
        'stdout': stdout,
        'stderr': completed.stderr.strip(),
    }


def validate_fly_config() -> dict[str, Any]:
    script = ROOT / 'scripts' / 'validate_fly_runtime_config.py'
    payload = _run_json_command([sys.executable, str(script)])
    return {
        'track': 'fly_config',
        'ok': bool(payload.get('ok')),
        'source': 'live',
        'detail': payload,
    }


def validate_docker_smoke(*, skip: bool) -> dict[str, Any]:
    if skip:
        return {'track': 'docker_smoke', 'ok': True, 'source': 'skipped', 'detail': {'reason': 'skip_docker=true'}}
    dockerfile = ROOT / 'Dockerfile.fly'
    if not dockerfile.exists():
        return {'track': 'docker_smoke', 'ok': False, 'source': 'live', 'detail': {'error': 'Dockerfile.fly ausente'}}
    completed = subprocess.run(
        ['docker', 'build', '-f', str(dockerfile), '-t', 'reqsys-api:runtime-public-smoke', str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        'track': 'docker_smoke',
        'ok': completed.returncode == 0,
        'source': 'live',
        'detail': {
            'exit_code': completed.returncode,
            'stderr_tail': '\n'.join(completed.stderr.strip().splitlines()[-5:]),
        },
    }


def validate_public_probe(*, base_url: str, environment: str, timeout: float, include_optional: bool) -> dict[str, Any]:
    script = ROOT / 'scripts' / 'validate_public_runtime.py'
    output = ROOT / 'artifacts' / 'runtime' / 'runtime-public-probe.json'
    readiness = ROOT / 'artifacts' / 'runtime' / 'runtime-public-readiness.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script),
        '--base-url',
        base_url,
        '--environment',
        environment,
        '--timeout',
        str(timeout),
        '--output',
        str(output),
        '--readiness-output',
        str(readiness),
    ]
    if include_optional:
        command.append('--include-optional-evidence')
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    probe_payload: dict[str, Any] = {}
    if output.exists():
        probe_payload = json.loads(output.read_text(encoding='utf-8'))
    readiness_payload: dict[str, Any] = {}
    if readiness.exists():
        readiness_payload = json.loads(readiness.read_text(encoding='utf-8'))
    if probe_payload:
        ok = probe_payload.get('failed', 1) == 0
    return {
        'track': 'public_probe',
        'ok': ok,
        'source': 'live',
        'detail': {
            'exit_code': completed.returncode,
            'base_url': base_url,
            'probe_artifact': str(output.relative_to(ROOT)),
            'readiness': readiness_payload or probe_payload.get('readiness', {}),
            'success_percentual': probe_payload.get('success_percentual'),
        },
    }


def load_fallback_cache(artifact_root: Path) -> dict[str, Any]:
    for relative in FALLBACK_CANDIDATES:
        candidate = artifact_root / relative
        if not candidate.exists():
            continue
        payload = json.loads(candidate.read_text(encoding='utf-8'))
        readiness = payload.get('readiness') or {}
        ok = readiness.get('operational_status') in {'healthy', 'partial'}
        return {
            'track': 'fallback_cache',
            'ok': ok,
            'source': 'artifact',
            'detail': {
                'path': str(candidate),
                'operational_status': readiness.get('operational_status', 'unknown'),
                'readiness_percent': readiness.get('readiness_percent'),
                'validated_at_epoch': payload.get('validated_at_epoch'),
            },
        }
    return {
        'track': 'fallback_cache',
        'ok': False,
        'source': 'missing',
        'detail': {'paths_tried': [str(artifact_root / path) for path in FALLBACK_CANDIDATES]},
    }


def build_summary(tracks: list[dict[str, Any]], *, probe_requested: bool) -> dict[str, Any]:
    by_name = {track['track']: track for track in tracks}
    config_ok = by_name.get('fly_config', {}).get('ok', False)
    docker_ok = by_name.get('docker_smoke', {}).get('ok', False)
    probe = by_name.get('public_probe')
    fallback = by_name.get('fallback_cache', {})
    probe_ok = probe.get('ok') if probe else None
    live_probe = probe is not None and probe.get('source') == 'live'

    if live_probe and probe_ok is False and fallback.get('ok'):
        operational_status = 'degraded_with_fallback'
        confidence = 'medium'
    elif live_probe and probe_ok:
        operational_status = 'healthy'
        confidence = 'high'
    elif config_ok and docker_ok and not probe_requested:
        operational_status = 'config_ready'
        confidence = 'medium'
    elif config_ok and fallback.get('ok'):
        operational_status = 'cached_evidence'
        confidence = 'low'
    elif config_ok:
        operational_status = 'config_only'
        confidence = 'low'
    else:
        operational_status = 'blocked'
        confidence = 'low'

    blocking: list[str] = []
    if not config_ok:
        blocking.append('fly_config_invalid')
    if not docker_ok:
        blocking.append('docker_smoke_failed')
    if probe_requested and live_probe and not probe_ok and not fallback.get('ok'):
        blocking.append('public_probe_failed_without_fallback')

    return {
        'operational_status': operational_status,
        'confidence': confidence,
        'config_ready': config_ok,
        'docker_ready': docker_ok,
        'probe_ready': probe_ok,
        'fallback_available': bool(fallback.get('ok')),
        'blocking_issues': blocking,
        'next_actions': [] if not blocking else [
            'Corrigir achados em fly_config ou docker_smoke antes de deploy',
            'Reexecutar probe com --probe quando URL pública estiver disponível',
            'Publicar artifact em audit/runtime/ para fallback governado',
        ],
    }


def build_payload(
    tracks: list[dict[str, Any]],
    *,
    probe_requested: bool,
    base_url: str | None,
    environment: str,
) -> dict[str, Any]:
    summary = build_summary(tracks, probe_requested=probe_requested)
    return {
        'schema_version': '1.0.0',
        'contract': 'trilha-a-runtime-publico',
        'validated_at_epoch': int(time.time()),
        'environment': environment,
        'base_url': base_url,
        'tracks': tracks,
        'summary': summary,
        'ok': not summary['blocking_issues'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Validador consolidado Trilha A — Runtime Público')
    parser.add_argument('--environment', default='prod')
    parser.add_argument('--base-url', default='https://reqsys-api.fly.dev')
    parser.add_argument('--probe', action='store_true', help='Executa probe HTTP público read-only')
    parser.add_argument('--include-optional-evidence', action='store_true')
    parser.add_argument('--timeout', type=float, default=10.0)
    parser.add_argument('--skip-docker', action='store_true')
    parser.add_argument('--artifact-root', default='.', help='Raiz para fallback de artifacts')
    parser.add_argument('--output', default='artifacts/runtime/runtime-public-validation.json')
    parser.add_argument('--strict', action='store_true', help='Falha quando houver blocking_issues')
    args = parser.parse_args()

    tracks: list[dict[str, Any]] = [
        validate_fly_config(),
        validate_docker_smoke(skip=args.skip_docker),
    ]

    if args.probe:
        tracks.append(
            validate_public_probe(
                base_url=args.base_url,
                environment=args.environment,
                timeout=args.timeout,
                include_optional=args.include_optional_evidence,
            )
        )
    else:
        tracks.append(load_fallback_cache(Path(args.artifact_root)))

    payload = build_payload(
        tracks,
        probe_requested=args.probe,
        base_url=args.base_url if args.probe else None,
        environment=args.environment,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.strict and payload['summary']['blocking_issues']:
        return 1
    return 0 if payload['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
