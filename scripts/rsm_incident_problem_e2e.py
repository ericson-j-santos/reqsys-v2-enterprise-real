#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
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
    return response.json()['data']


def _post(session: requests.Session, url: str, body: dict, correlation_id: str):
    return session.post(
        url,
        json=body,
        headers={'X-Correlation-ID': correlation_id},
        timeout=20,
    )


def _active_service(database_url: str) -> str:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT servico_id FROM gestao_ti_servicos '
                'WHERE ativo = true ORDER BY codigo LIMIT 1'
            )
            row = cur.fetchone()
            _assert(row is not None, 'nenhum ServicoTI ativo para RSM-08')
            return str(row[0])


def _counts(database_url: str, incident_id: str, problem_id: str) -> dict:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*), MIN(correlation_id) '
                'FROM rsm_incident_problem_links '
                'WHERE incident_case_id = %s AND problem_case_id = %s',
                (incident_id, problem_id),
            )
            relation_count, relation_correlation = cur.fetchone()
            cur.execute(
                'SELECT COUNT(*), MIN(statement), MIN(evidence_sha256), MIN(correlation_id) '
                'FROM rsm_problem_root_causes WHERE problem_case_id = %s',
                (problem_id,),
            )
            rca_count, statement, evidence_sha256, rca_correlation = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM rsm_service_case_events "
                "WHERE case_id = %s AND event_type = 'INCIDENT_LINKED_TO_PROBLEM'",
                (incident_id,),
            )
            relation_event_count = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM rsm_service_case_events "
                "WHERE case_id = %s AND event_type = 'PROBLEM_ROOT_CAUSE_RECORDED'",
                (problem_id,),
            )
            rca_event_count = int(cur.fetchone()[0])
            return {
                'relation_count': int(relation_count),
                'relation_correlation_id': relation_correlation,
                'root_cause_count': int(rca_count),
                'root_cause_statement': statement,
                'root_cause_evidence_sha256': evidence_sha256,
                'root_cause_correlation_id': rca_correlation,
                'relation_event_count': relation_event_count,
                'root_cause_event_count': rca_event_count,
            }


def run(base_url: str, database_url: str, expected_sha: str) -> dict:
    session = requests.Session()
    login = _data(
        session.post(
            base_url.rstrip('/') + '/v1/auth/login',
            json={'email': 'rsm-e2e@example.com'},
            timeout=20,
        )
    )
    session.headers.update({'Authorization': f"Bearer {login['access_token']}"})

    expected_sha = expected_sha.strip().lower()
    _assert(
        len(expected_sha) in {40, 64}
        and all(ch in '0123456789abcdef' for ch in expected_sha),
        'expected_sha inválido',
    )
    build_info = _data(session.get(base_url.rstrip('/') + '/api/runtime/build-info', timeout=20))
    runtime_sha = str(build_info.get('build_sha') or '').strip().lower()
    _assert(runtime_sha == expected_sha, 'runtime SHA divergente do HEAD esperado')

    service_id = _active_service(database_url)
    correlation_id = f'rsm08-{uuid4().hex}'

    def create_case(case_type: str, logical: str) -> dict:
        payload = {
            'case_type': case_type,
            'service_id': service_id,
            'requester': 'rsm-08-e2e',
            'impact': 'HIGH',
            'urgency': 'HIGH',
            'idempotency_key': _sha(logical),
            'event_id': str(uuid4()),
            'source': 'reqsys',
        }
        result = _data(
            _post(
                session,
                base_url.rstrip('/') + '/v1/service-cases',
                payload,
                correlation_id,
            )
        )
        _assert(result['duplicate'] is False, f'{case_type} inicial marcado como duplicado')
        return result['case']

    incident = create_case('INCIDENT', f'incident-{uuid4().hex}')
    problem = create_case('PROBLEM', f'problem-{uuid4().hex}')
    request_control = create_case('REQUEST', f'request-{uuid4().hex}')

    link_event_id = str(uuid4())
    link_payload = {'problem_case_id': problem['case_id'], 'event_id': link_event_id}
    link = _data(
        _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{incident['case_id']}/problem-links",
            link_payload,
            correlation_id,
        )
    )
    _assert(link['duplicate'] is False, 'primeiro vínculo marcado como duplicado')

    root_cause_event_id = str(uuid4())
    root_cause_payload = {
        'event_id': root_cause_event_id,
        'statement': 'Configuração de pool insuficiente reproduzida sob carga controlada.',
        'evidence_uri': f'urn:reqsys:rsm08:{correlation_id}:root-cause',
        'evidence_sha256': _sha(correlation_id + ':root-cause'),
    }
    root_cause = _data(
        _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{problem['case_id']}/root-causes",
            root_cause_payload,
            correlation_id,
        )
    )
    _assert(root_cause['duplicate'] is False, 'primeira causa raiz marcada como duplicada')

    incident_read = _data(
        session.get(
            base_url.rstrip('/') + f"/v1/service-cases/{incident['case_id']}",
            timeout=20,
        )
    )
    _assert(
        len(incident_read['related_cases']) == 1
        and incident_read['related_cases'][0]['case_id'] == problem['case_id']
        and incident_read['related_cases'][0]['case_type'] == 'PROBLEM',
        'GET do INCIDENT não expôs o PROBLEM relacionado',
    )

    problem_read = _data(
        session.get(
            base_url.rstrip('/') + f"/v1/service-cases/{problem['case_id']}",
            timeout=20,
        )
    )
    _assert(
        len(problem_read['root_causes']) == 1
        and problem_read['root_causes'][0]['statement'] == root_cause_payload['statement'],
        'GET do PROBLEM não expôs a causa raiz persistida',
    )

    first_readback = _counts(database_url, incident['case_id'], problem['case_id'])
    _assert(first_readback['relation_count'] == 1, 'relação ausente no PostgreSQL')
    _assert(first_readback['root_cause_count'] == 1, 'causa raiz ausente no PostgreSQL')
    _assert(first_readback['relation_event_count'] == 1, 'evento de relação ausente')
    _assert(first_readback['root_cause_event_count'] == 1, 'evento de causa raiz ausente')
    _assert(
        first_readback['root_cause_evidence_sha256'] == root_cause_payload['evidence_sha256'],
        'digest da evidência divergiu na leitura independente',
    )

    link_replay = _data(
        _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{incident['case_id']}/problem-links",
            link_payload,
            correlation_id,
        )
    )
    _assert(link_replay['duplicate'] is True, 'replay do event_id não convergiu')

    logical_replay = _data(
        _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{incident['case_id']}/problem-links",
            {'problem_case_id': problem['case_id'], 'event_id': str(uuid4())},
            correlation_id,
        )
    )
    _assert(logical_replay['duplicate'] is True, 'replay da identidade lógica não convergiu')

    rca_replay = _data(
        _post(
            session,
            base_url.rstrip('/') + f"/v1/service-cases/{problem['case_id']}/root-causes",
            root_cause_payload,
            correlation_id,
        )
    )
    _assert(rca_replay['duplicate'] is True, 'replay da causa raiz não convergiu')

    after_replay = _counts(database_url, incident['case_id'], problem['case_id'])
    _assert(after_replay == first_readback, 'replay alterou a persistência')

    negative = _post(
        session,
        base_url.rstrip('/') + f"/v1/service-cases/{request_control['case_id']}/problem-links",
        {'problem_case_id': problem['case_id'], 'event_id': str(uuid4())},
        correlation_id,
    )
    _assert(negative.status_code == 422, f'origem não INCIDENT retornou {negative.status_code}')
    after_negative = _counts(database_url, incident['case_id'], problem['case_id'])
    _assert(after_negative == first_readback, 'controle negativo deixou mutação')

    test_of_test = _post(
        session,
        base_url.rstrip('/') + f"/v1/service-cases/{problem['case_id']}/root-causes",
        {
            'event_id': str(uuid4()),
            'statement': 'entrada deliberadamente inválida',
            'evidence_uri': 'urn:reqsys:rsm08:test-of-test',
            'evidence_sha256': 'invalid',
        },
        correlation_id,
    )
    _assert(test_of_test.status_code == 422, 'teste do teste não detectou SHA-256 inválido')
    after_test_of_test = _counts(database_url, incident['case_id'], problem['case_id'])
    _assert(after_test_of_test == first_readback, 'teste do teste deixou resíduo')

    return {
        'status': 'passed',
        'environment': build_info.get('environment'),
        'sha': runtime_sha,
        'expected_sha': expected_sha,
        'correlation_id': correlation_id,
        'incident_case_id': incident['case_id'],
        'problem_case_id': problem['case_id'],
        'positive': 'passed',
        'negative_control': 'passed',
        'replay': 'passed',
        'logical_identity_replay': 'passed',
        'test_of_test': 'passed',
        'independent_readback': 'postgresql',
        'readback': first_readback,
        'production_touched': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = run(args.base_url, args.database_url, args.expected_sha)
    except Exception as exc:
        evidence = {
            'status': 'failed',
            'error': type(exc).__name__,
            'detail': 'rsm-08-e2e-failed',
            'production_touched': False,
        }
        code = 2
    else:
        code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(json.dumps(evidence, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
