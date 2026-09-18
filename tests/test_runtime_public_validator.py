"""Testes do validador consolidado Trilha A — Runtime Público."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime_public_validator import build_payload, build_summary, load_fallback_cache


def test_build_summary_config_ready_without_probe():
    tracks = [
        {'track': 'fly_config', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'docker_smoke', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'fallback_cache', 'ok': False, 'source': 'missing', 'detail': {}},
    ]
    summary = build_summary(tracks, probe_requested=False)

    assert summary['operational_status'] == 'config_ready'
    assert summary['confidence'] == 'medium'
    assert summary['blocking_issues'] == []


def test_build_summary_degraded_with_fallback_when_probe_fails(tmp_path: Path):
    cache = tmp_path / 'audit' / 'runtime' / 'public-runtime-validation.json'
    cache.parent.mkdir(parents=True)
    cache.write_text(
        json.dumps(
            {
                'readiness': {'operational_status': 'partial', 'readiness_percent': 75},
                'validated_at_epoch': 1,
            }
        ),
        encoding='utf-8',
    )
    fallback = load_fallback_cache(tmp_path)
    tracks = [
        {'track': 'fly_config', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'docker_smoke', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'public_probe', 'ok': False, 'source': 'live', 'detail': {'success_percentual': 25}},
        fallback,
    ]
    summary = build_summary(tracks, probe_requested=True)

    assert summary['operational_status'] == 'degraded_with_fallback'
    assert summary['fallback_available'] is True
    assert summary['blocking_issues'] == []


def test_build_summary_blocks_when_config_invalid():
    tracks = [
        {'track': 'fly_config', 'ok': False, 'source': 'live', 'detail': {'errors': ['x']}},
        {'track': 'docker_smoke', 'ok': False, 'source': 'live', 'detail': {}},
        {'track': 'fallback_cache', 'ok': False, 'source': 'missing', 'detail': {}},
    ]
    summary = build_summary(tracks, probe_requested=False)

    assert summary['operational_status'] == 'blocked'
    assert 'fly_config_invalid' in summary['blocking_issues']


def test_build_payload_marks_ok_when_no_blocking():
    tracks = [
        {'track': 'fly_config', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'docker_smoke', 'ok': True, 'source': 'live', 'detail': {}},
        {'track': 'fallback_cache', 'ok': False, 'source': 'missing', 'detail': {}},
    ]
    payload = build_payload(tracks, probe_requested=False, base_url=None, environment='prod')

    assert payload['contract'] == 'trilha-a-runtime-publico'
    assert payload['ok'] is True
    assert payload['summary']['operational_status'] == 'config_ready'
