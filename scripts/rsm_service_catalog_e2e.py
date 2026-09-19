#!/usr/bin/env python3
"""E2E RSM-03: catálogo mínimo Service -> ServiceOffering -> ServiceCase(REQUEST).

Executa contra API HTTP real e PostgreSQL real. Cobre caso positivo, controles
negativos (oferta inexistente, oferta inativa, campo obrigatório ausente, campo
não declarado, tipo divergente), replay idempotente e leitura independente por
conexão própria ao banco. Evidência fica presa ao SHA exato do runtime.
"""

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


def _post(session: requests.Session, url: str, *, json_body: dict, correlation_id: str):
    return session.post(
        url,
        json=json_body,
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
            _assert(row is not None, 'nenhum ServicoTI ativo disponível para o E2E')
            return str(row[0])


def _catalog_readback(database_url: str, idempotency_key: str) -> dict:
    """Leitura independente do vínculo catálogo -> caso, sem passar pela API."""
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT c.case_id, c.case_type, c.state, c.service_id, c.correlation_id, '
                '       l.offering_id, l.submitted_fields, o.code, o.active '
                'FROM rsm_service_cases c '
                'JOIN rsm_service_case_offerings l ON l.case_id = c.case_id '
                'JOIN rsm_service_offerings o ON o.offering_id = l.offering_id '
                'WHERE c.idempotency_key = %s',
                (idempotency_key,),
            )
            row = cur.fetchone()
            _assert(row is not None, 'vínculo catálogo -> caso ausente na leitura independente')
            cur.execute(
                'SELECT COUNT(*) FROM rsm_service_cases WHERE idempotency_key = %s',
                (idempotency_key,),
            )
            case_count = int(cur.fetchone()[0])
            cur.execute(
                'SELECT COUNT(*) FROM rsm_service_case_offerings WHERE case_id = %s',
                (row[0],),
            )
            link_count = int(cur.fetchone()[0])
            submitted = row[6]
            if isinstance(submitted, str):
                submitted = json.loads(submitted)
            return {
                'case_id': row[0],
                'case_type': row[1],
                'state': row[2],
                'service_id': row[3],
                'correlation_id': row[4],
                'offering_id': row[5],
                'submitted_fields': submitted,
                'offering_code': row[7],
                'offering_active': bool(row[8]),
                'case_count': case_count,
                'link_count': link_count,
            }


def _count_cases(database_url: str, idempotency_key: str) -> int:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) FROM rsm_service_cases WHERE idempotency_key = %s',
                (idempotency_key,),
            )
            return int(cur.fetchone()[0])


FIELD_SCHEMA = {
    'schema_version': '1.0.0',
    'fields': [
        {
            'key': 'justificativa',
            'label': 'Justificativa',
            'type': 'STRING',
            'required': True,
            'max_length': 120,
        },
        {
            'key': 'ambiente',
            'label': 'Ambiente',
            'type': 'ENUM',
            'required': True,
            'options': ['DEV', 'HML'],
        },
        {
            'key': 'quantidade',
            'label': 'Quantidade',
            'type': 'INTEGER',
            'min_value': 1,
            'max_value': 10,
        },
    ],
}


def run(base_url: str, database_url: str, expected_sha: str) -> dict:
    base = base_url.rstrip('/')
    correlation_id = f'rsm1785-{uuid4().hex}'
    service_id = _active_service(database_url)
    session = requests.Session()

    login = session.post(
        base + '/v1/auth/login',
        json={'email': 'rsm-catalog-e2e@example.com'},
        timeout=20,
    )
    login_data = _data(login)
    session.headers.update({'Authorization': f"Bearer {login_data['access_token']}"})

    expected_sha = expected_sha.strip().lower()
    _assert(
        len(expected_sha) in {40, 64} and all(ch in '0123456789abcdef' for ch in expected_sha),
        'expected_sha deve ser SHA Git completo hexadecimal',
    )
    build_info = _data(session.get(base + '/api/runtime/build-info', timeout=20))
    runtime_sha = str(build_info.get('build_sha') or '').strip().lower()
    _assert(
        runtime_sha == expected_sha,
        f'build-info SHA divergente: esperado={expected_sha} observado={runtime_sha}',
    )

    # --- catálogo: oferta ativa e oferta inativa (controle negativo) ---
    active_code = f'E2E-ATIVA-{uuid4().hex[:8].upper()}'
    inactive_code = f'E2E-INATIVA-{uuid4().hex[:8].upper()}'
    offering = _data(
        _post(
            session,
            base + '/v1/service-offerings',
            json_body={
                'service_id': service_id,
                'code': active_code,
                'name': 'Oferta E2E ativa',
                'description': 'RSM-03 catálogo mínimo',
                'active': True,
                'field_schema': FIELD_SCHEMA,
            },
            correlation_id=correlation_id,
        )
    )
    _assert(offering['duplicate'] is False, 'primeiro registro de oferta marcado como duplicado')
    offering_id = offering['offering']['offering_id']

    offering_replay = _data(
        _post(
            session,
            base + '/v1/service-offerings',
            json_body={
                'service_id': service_id,
                'code': active_code,
                'name': 'Oferta E2E ativa',
                'active': True,
                'field_schema': FIELD_SCHEMA,
            },
            correlation_id=correlation_id,
        )
    )
    _assert(offering_replay['duplicate'] is True, 'replay de oferta não foi idempotente')
    _assert(
        offering_replay['offering']['offering_id'] == offering_id,
        'replay de oferta convergiu para outro offering_id',
    )

    inactive = _data(
        _post(
            session,
            base + '/v1/service-offerings',
            json_body={
                'service_id': service_id,
                'code': inactive_code,
                'name': 'Oferta E2E inativa',
                'active': False,
                'field_schema': FIELD_SCHEMA,
            },
            correlation_id=correlation_id,
        )
    )
    inactive_offering_id = inactive['offering']['offering_id']

    # --- caso positivo: abertura de REQUEST a partir da oferta ativa ---
    logical_id = f'rsm-catalog-{uuid4().hex}'
    idempotency_key = _sha(logical_id)
    fields = {'justificativa': 'acesso mensal ao relatorio', 'ambiente': 'DEV', 'quantidade': 2}
    request_payload = {
        'requester': 'rsm-catalog-e2e',
        'impact': 'MEDIUM',
        'urgency': 'HIGH',
        'idempotency_key': idempotency_key,
        'event_id': str(uuid4()),
        'source': 'reqsys',
        'fields': fields,
    }
    created = _data(
        _post(
            session,
            base + f'/v1/service-offerings/{offering_id}/requests',
            json_body=request_payload,
            correlation_id=correlation_id,
        )
    )
    _assert(created['duplicate'] is False, 'primeira abertura marcada como duplicada')
    _assert(created['case']['case_type'] == 'REQUEST', 'caso aberto não é REQUEST')
    _assert(created['case']['service_id'] == service_id, 'caso aberto em serviço divergente')
    _assert(created['offering_id'] == offering_id, 'caso não vinculado à oferta usada')
    case_id = created['case']['case_id']

    readback = _catalog_readback(database_url, idempotency_key)
    _assert(readback['case_id'] == case_id, 'leitura independente divergiu do case_id')
    _assert(readback['case_type'] == 'REQUEST', 'leitura independente não confirmou REQUEST')
    _assert(readback['state'] == 'NEW', 'estado inicial persistido não é NEW')
    _assert(readback['offering_id'] == offering_id, 'vínculo persistido aponta para outra oferta')
    _assert(readback['offering_code'] == active_code, 'code da oferta divergiu na leitura independente')
    _assert(readback['submitted_fields'] == fields, 'campos persistidos divergem da entrada válida')
    _assert(readback['correlation_id'] == correlation_id, 'correlation_id não propagou para o vínculo')
    _assert(readback['case_count'] == 1, 'mais de um caso persistido no caso positivo')
    _assert(readback['link_count'] == 1, 'mais de um vínculo persistido no caso positivo')

    # --- replay: mesma idempotency_key não cria segundo caso ---
    replay_payload = dict(request_payload)
    replay_payload['event_id'] = str(uuid4())
    replay = _data(
        _post(
            session,
            base + f'/v1/service-offerings/{offering_id}/requests',
            json_body=replay_payload,
            correlation_id=correlation_id,
        )
    )
    _assert(replay['duplicate'] is True, 'replay não foi marcado como duplicado')
    _assert(replay['case']['case_id'] == case_id, 'replay convergiu para outro caso')
    replay_readback = _catalog_readback(database_url, idempotency_key)
    _assert(replay_readback['case_count'] == 1, 'replay criou caso adicional')
    _assert(replay_readback['link_count'] == 1, 'replay criou vínculo adicional')

    # --- controles negativos ---
    negative_controls = {}

    missing_offering = _post(
        session,
        base + f'/v1/service-offerings/{uuid4()}/requests',
        json_body={**request_payload, 'idempotency_key': _sha(f'nf-{uuid4().hex}'), 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(
        missing_offering.status_code == 404,
        f'oferta inexistente retornou HTTP {missing_offering.status_code}',
    )
    negative_controls['offering_not_found'] = 'passed'

    inactive_key = _sha(f'inativa-{uuid4().hex}')
    inactive_response = _post(
        session,
        base + f'/v1/service-offerings/{inactive_offering_id}/requests',
        json_body={**request_payload, 'idempotency_key': inactive_key, 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(
        inactive_response.status_code == 409,
        f'oferta inativa retornou HTTP {inactive_response.status_code}',
    )
    _assert(_count_cases(database_url, inactive_key) == 0, 'oferta inativa persistiu caso')
    negative_controls['offering_inactive'] = 'passed'

    invalid_cases = {
        'required_field_missing': {'ambiente': 'DEV'},
        'undeclared_field': {'justificativa': 'ok', 'ambiente': 'DEV', 'nao_declarado': 'x'},
        'enum_out_of_options': {'justificativa': 'ok', 'ambiente': 'PROD'},
        'integer_type_mismatch': {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': '2'},
        'string_over_max_length': {'justificativa': 'x' * 200, 'ambiente': 'DEV'},
    }
    for name, invalid_fields in invalid_cases.items():
        invalid_key = _sha(f'{name}-{uuid4().hex}')
        response = _post(
            session,
            base + f'/v1/service-offerings/{offering_id}/requests',
            json_body={
                **request_payload,
                'idempotency_key': invalid_key,
                'event_id': str(uuid4()),
                'fields': invalid_fields,
            },
            correlation_id=correlation_id,
        )
        _assert(response.status_code == 422, f'{name} retornou HTTP {response.status_code}')
        _assert(_count_cases(database_url, invalid_key) == 0, f'{name} persistiu caso indevido')
        negative_controls[name] = 'passed'

    # --- teste do teste: falha conhecida deve ser detectada ---
    bad_key = _post(
        session,
        base + f'/v1/service-offerings/{offering_id}/requests',
        json_body={**request_payload, 'idempotency_key': 'invalid', 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(
        bad_key.status_code == 422,
        f'teste do teste não detectou idempotency_key inválida: {bad_key.status_code}',
    )

    final_readback = _catalog_readback(database_url, idempotency_key)
    _assert(final_readback['case_count'] == 1, 'controles negativos criaram caso adicional')
    _assert(final_readback['state'] == 'NEW', 'controles negativos alteraram o estado do caso')

    return {
        'status': 'passed',
        'increment': 'RSM-03',
        'environment': build_info.get('environment'),
        'sha': runtime_sha,
        'expected_sha': expected_sha,
        'correlation_id': correlation_id,
        'idempotency_key': idempotency_key,
        'service_id': service_id,
        'offering_id': offering_id,
        'offering_code': active_code,
        'case_id': case_id,
        'input': request_payload,
        'expected': 'REQUEST vinculado à oferta ativa, replay sem segundo caso e entrada inválida sem efeito',
        'observed': {
            'created': readback,
            'replay': replay_readback,
            'final': final_readback,
        },
        'independent_readback': 'postgresql',
        'positive': 'passed',
        'negative_control': negative_controls,
        'replay': 'passed',
        'test_of_test': 'passed',
        'async_applicable': False,
        'production_touched': False,
        'secrets_used': False,
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
