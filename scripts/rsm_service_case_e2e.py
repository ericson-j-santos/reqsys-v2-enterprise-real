#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg2
import requests


def _sql_url(value: str) -> str:
    return value.replace('postgresql+psycopg2://', 'postgresql://', 1)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _data(response: requests.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    return payload['data']


def _post(session: requests.Session, url: str, *, json_body: dict, correlation_id: str):
    return session.post(
        url,
        json=json_body,
        headers={'X-Correlation-ID': correlation_id},
        timeout=20,
    )


def _db_read(database_url: str, idempotency_key: str) -> dict:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT case_id, state, version, correlation_id '
                'FROM rsm_service_cases WHERE idempotency_key = %s',
                (idempotency_key,),
            )
            row = cur.fetchone()
            _assert(row is not None, 'ServiceCase ausente na leitura independente')
            cur.execute(
                'SELECT COUNT(*) FROM rsm_service_cases WHERE idempotency_key = %s',
                (idempotency_key,),
            )
            case_count = int(cur.fetchone()[0])
            cur.execute(
                'SELECT COUNT(*) FROM rsm_service_case_events WHERE case_id = %s',
                (row[0],),
            )
            event_count = int(cur.fetchone()[0])
            return {
                'case_id': row[0],
                'state': row[1],
                'version': int(row[2]),
                'correlation_id': row[3],
                'case_count': case_count,
                'event_count': event_count,
            }


def _active_service(database_url: str) -> str:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT servico_id FROM gestao_ti_servicos '
                'WHERE ativo = true ORDER BY codigo LIMIT 1'
            )
            row = cur.fetchone()
            _assert(row is not None, 'nenhum ServicoTI ativo disponível para o E2E')
            return str(row[0])


def run(base_url: str, database_url: str) -> dict:
    correlation_id = f'rsm1788-{uuid4().hex}'
    logical_id = f'rsm-e2e-{uuid4().hex}'
    idempotency_key = _sha(logical_id)
    service_id = _active_service(database_url)
    session = requests.Session()

    login = session.post(
        base_url.rstrip('/') + '/v1/auth/login',
        json={'email': 'rsm-e2e@example.invalid'},
        timeout=20,
    )
    login_data = _data(login)
    session.headers.update({'Authorization': f"Bearer {login_data['access_token']}"})

    build_info = _data(session.get(base_url.rstrip('/') + '/api/runtime/build-info', timeout=20))
    create_payload = {
        'case_type': 'REQUEST',
        'service_id': service_id,
        'requester': 'rsm-e2e',
        'impact': 'MEDIUM',
        'urgency': 'HIGH',
        'idempotency_key': idempotency_key,
        'event_id': str(uuid4()),
        'source': 'reqsys',
    }
    created = _data(
        _post(
            session,
            base_url.rstrip('/') + '/v1/service-cases',
            json_body=create_payload,
            correlation_id=correlation_id,
        )
    )
    case = created['case']
    _assert(created['duplicate'] is False, 'primeira criação marcada como duplicada')

    initial_db = _db_read(database_url, idempotency_key)
    _assert(initial_db['case_id'] == case['case_id'], 'leitura independente divergiu do case_id')
    _assert(initial_db['state'] == 'NEW', 'estado inicial persistido não é NEW')

    transitions = []
    for target in ('TRIAGE', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'):
        body = {
            'target_state': target,
            'expected_version': case['version'],
            'event_id': str(uuid4()),
        }
        if target == 'RESOLVED':
            body['evidence_uri'] = f'urn:reqsys:rsm-e2e:{correlation_id}'
            body['evidence_sha256'] = _sha(correlation_id)
        response = _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{case['case_id']}/transitions",
            json_body=body,
            correlation_id=correlation_id,
        )
        data = _data(response)
        case = data['case']
        transitions.append({'target': target, 'state': case['state'], 'version': case['version']})

    terminal_db = _db_read(database_url, idempotency_key)
    _assert(terminal_db['state'] == 'CLOSED', 'leitura independente não confirmou CLOSED')
    _assert(terminal_db['case_count'] == 1, 'mais de um caso persistido antes do replay')

    replay_payload = dict(create_payload)
    replay_payload['event_id'] = str(uuid4())
    replay = _data(
        _post(
            session,
            base_url.rstrip('/') + '/v1/service-cases',
            json_body=replay_payload,
            correlation_id=correlation_id,
        )
    )
    _assert(replay['duplicate'] is True, 'replay não foi marcado como duplicado')
    _assert(replay['case']['case_id'] == case['case_id'], 'replay convergiu para outro caso')

    replay_db = _db_read(database_url, idempotency_key)
    _assert(replay_db['case_count'] == 1, 'replay criou caso adicional')
    _assert(replay_db['state'] == 'CLOSED', 'replay alterou estado terminal')

    events_before_negative = replay_db['event_count']
    invalid = _post(
        session,
        base_url.rstrip('/') + f"/v1/service-cases/{case['case_id']}/transitions",
        json_body={
            'target_state': 'IN_PROGRESS',
            'expected_version': case['version'],
            'event_id': str(uuid4()),
        },
        correlation_id=correlation_id,
    )
    _assert(invalid.status_code == 409, f'controle negativo retornou HTTP {invalid.status_code}')
    negative_db = _db_read(database_url, idempotency_key)
    _assert(negative_db['state'] == 'CLOSED', 'controle negativo alterou estado')
    _assert(
        negative_db['event_count'] == events_before_negative,
        'controle negativo persistiu evento indevido',
    )

    bad_key = dict(create_payload)
    bad_key['event_id'] = str(uuid4())
    bad_key['idempotency_key'] = 'invalid'
    bad = _post(
        session,
        base_url.rstrip('/') + '/v1/service-cases',
        json_body=bad_key,
        correlation_id=correlation_id,
    )
    _assert(bad.status_code == 422, f'teste do teste não detectou chave inválida: {bad.status_code}')

    return {
        'status': 'passed',
        'environment': build_info.get('environment'),
        'sha': build_info.get('build_sha') or os.getenv('GITHUB_SHA') or 'unknown',
        'correlation_id': correlation_id,
        'idempotency_key': idempotency_key,
        'case_id': case['case_id'],
        'input': create_payload,
        'expected': 'CLOSED, replay sem duplicidade e transição inválida sem efeito',
        'observed': {
            'transitions': transitions,
            'terminal': terminal_db,
            'replay': replay_db,
        },
        'independent_readback': 'postgresql',
        'positive': 'passed',
        'negative_control': 'passed',
        'replay': 'passed',
        'test_of_test': 'passed',
        'async_applicable': False,
        'external_blockers': [
            'Teams real permanece fora desta fatia até readiness externa estar comprovada'
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = run(args.base_url, args.database_url)
    except Exception as exc:
        evidence = {'status': 'failed', 'error': type(exc).__name__, 'detail': str(exc)[:500]}
        code = 2
    else:
        code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
