#!/usr/bin/env python3
"""E2E RSM-04: SLA determinístico, atribuição, aprovação e histórico auditável.

Executa contra API HTTP real e PostgreSQL real. Cobre caso positivo, controles
negativos (portão de aprovação fail-closed, decisão terminal, relógio manipulado,
event_id reaproveitado), replay idempotente e leitura independente por conexão
própria ao banco. Evidência fica presa ao SHA exato do runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import requests

# Mesmo contrato de app.domain.service_operations.PRIORITY_SLA_FACTOR, replicado
# aqui de propósito: o E2E precisa recalcular o prazo esperado por fora do código
# sob teste, senão um erro no fator passaria despercebido.
PRIORITY_SLA_FACTOR = {'P1': 1, 'P2': 2, 'P3': 4, 'P4': 8}
RESPONSE_MINUTES = 30
RESOLUTION_MINUTES = 240


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
    return session.post(url, json=json_body, headers={'X-Correlation-ID': correlation_id}, timeout=20)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _read_operations(database_url: str, case_id: str) -> dict:
    """Leitura independente: SLA, atribuições, aprovações e histórico, via SQL."""
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT policy_id, priority, started_at, response_due_at, resolution_due_at, '
                '       correlation_id '
                'FROM rsm_case_sla WHERE case_id = %s',
                (case_id,),
            )
            sla_row = cur.fetchone()
            cur.execute(
                'SELECT sequence, assignment_group, assignee, previous_group, previous_assignee '
                'FROM rsm_case_assignments WHERE case_id = %s ORDER BY sequence',
                (case_id,),
            )
            assignments = [
                {
                    'sequence': int(row[0]),
                    'assignment_group': row[1],
                    'assignee': row[2],
                    'previous_group': row[3],
                    'previous_assignee': row[4],
                }
                for row in cur.fetchall()
            ]
            cur.execute(
                'SELECT sequence, approver, status, decision_reason '
                'FROM rsm_case_approvals WHERE case_id = %s ORDER BY sequence',
                (case_id,),
            )
            approvals = [
                {
                    'sequence': int(row[0]),
                    'approver': row[1],
                    'status': row[2],
                    'decision_reason': row[3],
                }
                for row in cur.fetchall()
            ]
            cur.execute(
                'SELECT event_type, COUNT(*) FROM rsm_service_case_events '
                'WHERE case_id = %s GROUP BY event_type ORDER BY event_type',
                (case_id,),
            )
            event_counts = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute('SELECT state, version FROM rsm_service_cases WHERE case_id = %s', (case_id,))
            case_row = cur.fetchone()
            _assert(case_row is not None, 'caso ausente na leitura independente')
            return {
                'sla': (
                    {
                        'policy_id': sla_row[0],
                        'priority': sla_row[1],
                        'started_at': _aware(sla_row[2]).isoformat(),
                        'response_due_at': _aware(sla_row[3]).isoformat(),
                        'resolution_due_at': _aware(sla_row[4]).isoformat(),
                        'correlation_id': sla_row[5],
                        '_started_at': _aware(sla_row[2]),
                        '_response_due_at': _aware(sla_row[3]),
                        '_resolution_due_at': _aware(sla_row[4]),
                    }
                    if sla_row
                    else None
                ),
                'assignments': assignments,
                'approvals': approvals,
                'event_counts': event_counts,
                'state': case_row[0],
                'version': int(case_row[1]),
            }


def _active_service(database_url: str) -> str:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT servico_id FROM gestao_ti_servicos WHERE ativo = true ORDER BY codigo LIMIT 1'
            )
            row = cur.fetchone()
            _assert(row is not None, 'nenhum ServicoTI ativo disponível para o E2E')
            return str(row[0])


def run(base_url: str, database_url: str, expected_sha: str) -> dict:
    base = base_url.rstrip('/')
    correlation_id = f'rsm1786-{uuid4().hex}'
    service_id = _active_service(database_url)
    session = requests.Session()

    login = session.post(base + '/v1/auth/login', json={'email': 'rsm-ops-e2e@example.com'}, timeout=20)
    session.headers.update({'Authorization': f"Bearer {_data(login)['access_token']}"})

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

    negative_controls: dict[str, str] = {}

    # --- política de SLA -------------------------------------------------
    policy_code = f'E2E-SLA-{uuid4().hex[:8].upper()}'
    policy_body = {
        'code': policy_code,
        'name': 'Politica E2E',
        'response_minutes': RESPONSE_MINUTES,
        'resolution_minutes': RESOLUTION_MINUTES,
    }
    policy = _data(_post(session, base + '/v1/sla-policies', json_body=policy_body, correlation_id=correlation_id))
    _assert(policy['duplicate'] is False, 'primeiro registro de política marcado como duplicado')
    policy_id = policy['policy']['policy_id']

    policy_replay = _data(
        _post(session, base + '/v1/sla-policies', json_body=policy_body, correlation_id=correlation_id)
    )
    _assert(policy_replay['duplicate'] is True, 'replay de política não foi idempotente')
    _assert(policy_replay['policy']['policy_id'] == policy_id, 'replay de política gerou outro policy_id')

    incoerente = _post(
        session,
        base + '/v1/sla-policies',
        json_body={
            'code': f'E2E-SLA-BAD-{uuid4().hex[:6].upper()}',
            'name': 'Incoerente',
            'response_minutes': 120,
            'resolution_minutes': 60,
        },
        correlation_id=correlation_id,
    )
    _assert(incoerente.status_code == 422, f'política incoerente retornou HTTP {incoerente.status_code}')
    negative_controls['policy_resolution_before_response'] = 'passed'

    # --- caso base -------------------------------------------------------
    idempotency_key = _sha(f'rsm-ops-{uuid4().hex}')
    case = _data(
        _post(
            session,
            base + '/v1/service-cases',
            json_body={
                'case_type': 'REQUEST',
                'service_id': service_id,
                'requester': 'rsm-ops-e2e',
                'impact': 'HIGH',
                'urgency': 'HIGH',
                'idempotency_key': idempotency_key,
                'event_id': str(uuid4()),
                'source': 'reqsys',
            },
            correlation_id=correlation_id,
        )
    )['case']
    case_id = case['case_id']
    priority = case['priority']
    _assert(priority in PRIORITY_SLA_FACTOR, f'prioridade fora do contrato: {priority}')

    # --- SLA determinístico ----------------------------------------------
    sla_event = str(uuid4())
    sla = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/sla',
            json_body={'policy_id': policy_id, 'event_id': sla_event},
            correlation_id=correlation_id,
        )
    )
    _assert(sla['duplicate'] is False, 'primeira aplicação de SLA marcada como duplicada')

    readback = _read_operations(database_url, case_id)
    _assert(readback['sla'] is not None, 'SLA ausente na leitura independente')
    factor = PRIORITY_SLA_FACTOR[priority]
    expected_response = readback['sla']['_started_at'] + timedelta(minutes=RESPONSE_MINUTES * factor)
    expected_resolution = readback['sla']['_started_at'] + timedelta(minutes=RESOLUTION_MINUTES * factor)
    _assert(
        readback['sla']['_response_due_at'] == expected_response,
        f"response_due_at divergente: {readback['sla']['_response_due_at']} != {expected_response}",
    )
    _assert(
        readback['sla']['_resolution_due_at'] == expected_resolution,
        f"resolution_due_at divergente: {readback['sla']['_resolution_due_at']} != {expected_resolution}",
    )
    _assert(readback['sla']['priority'] == priority, 'prioridade persistida divergente')
    sla_determinism = 'passed'

    sla_replay = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/sla',
            json_body={'policy_id': policy_id, 'event_id': sla_event},
            correlation_id=correlation_id,
        )
    )
    _assert(sla_replay['duplicate'] is True, 'replay de SLA não foi idempotente')
    _assert(sla_replay['sla'] == sla['sla'], 'replay de SLA alterou os prazos')
    after_sla_replay = _read_operations(database_url, case_id)
    _assert(
        after_sla_replay['event_counts'].get('SLA_APPLIED') == 1,
        'replay de SLA duplicou evento no histórico',
    )

    missing_policy = _post(
        session,
        base + f'/v1/service-cases/{case_id}/sla',
        json_body={'policy_id': str(uuid4()), 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(missing_policy.status_code == 404, f'política inexistente retornou HTTP {missing_policy.status_code}')
    negative_controls['sla_policy_not_found'] = 'passed'

    clock = session.get(
        base + f'/v1/service-cases/{case_id}/operations',
        params={'evaluated_at': '2000-01-01T00:00:00+00:00'},
        timeout=20,
    )
    _assert(clock.status_code == 422, f'relógio manipulado retornou HTTP {clock.status_code}')
    negative_controls['clock_before_case_start'] = 'passed'

    breached = _data(
        session.get(
            base + f'/v1/service-cases/{case_id}/operations',
            params={'evaluated_at': '2099-01-01T00:00:00+00:00'},
            timeout=20,
        )
    )
    _assert(
        breached['sla']['state'] == 'RESOLUTION_BREACHED',
        f"estado de SLA em instante futuro inesperado: {breached['sla']['state']}",
    )

    # --- atribuição auditável --------------------------------------------
    assign_event = str(uuid4())
    first_assignment = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/assignments',
            json_body={'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': assign_event},
            correlation_id=correlation_id,
        )
    )
    _assert(first_assignment['duplicate'] is False, 'primeira atribuição marcada como duplicada')
    _assert(
        first_assignment['assignment']['previous_group'] is None,
        'primeira atribuição registrou grupo anterior inexistente',
    )

    assign_replay = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/assignments',
            json_body={'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': assign_event},
            correlation_id=correlation_id,
        )
    )
    _assert(assign_replay['duplicate'] is True, 'replay de atribuição não foi idempotente')

    second_assignment = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/assignments',
            json_body={'assignment_group': 'Engenharia', 'assignee': 'bruno', 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )
    _assert(
        second_assignment['assignment']['previous_assignee'] == 'ana',
        'troca de responsável não registrou o anterior',
    )

    after_assign = _read_operations(database_url, case_id)
    _assert(len(after_assign['assignments']) == 2, 'histórico de atribuição divergente')
    _assert(
        [item['sequence'] for item in after_assign['assignments']] == [1, 2],
        'sequência do histórico de atribuição não é append-only',
    )
    _assert(
        after_assign['assignments'][0]['assignment_group'] == 'Sustentacao',
        'histórico de atribuição foi reescrito',
    )

    noop = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/assignments',
            json_body={'assignment_group': 'Engenharia', 'assignee': 'bruno', 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )
    _assert(noop['duplicate'] is True, 'reatribuição idêntica não foi tratada como no-op')
    _assert(
        len(_read_operations(database_url, case_id)['assignments']) == 2,
        'reatribuição idêntica criou registro extra',
    )

    invalid_assign = _post(
        session,
        base + f'/v1/service-cases/{case_id}/assignments',
        json_body={'assignment_group': '   ', 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(invalid_assign.status_code == 422, f'grupo vazio retornou HTTP {invalid_assign.status_code}')
    negative_controls['assignment_without_group'] = 'passed'

    reused_event = _post(
        session,
        base + f'/v1/service-cases/{case_id}/assignments',
        json_body={'assignment_group': 'Outro', 'event_id': sla_event},
        correlation_id=correlation_id,
    )
    _assert(reused_event.status_code == 409, f'event_id reaproveitado retornou HTTP {reused_event.status_code}')
    negative_controls['event_id_reused_for_other_effect'] = 'passed'

    # --- portão de aprovação fail-closed ---------------------------------
    version = case['version']
    triage = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/transitions',
            json_body={'target_state': 'TRIAGE', 'expected_version': version, 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )
    version = triage['case']['version']
    pending = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/transitions',
            json_body={'target_state': 'PENDING_APPROVAL', 'expected_version': version, 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )
    version = pending['case']['version']

    def _try_advance() -> requests.Response:
        return _post(
            session,
            base + f'/v1/service-cases/{case_id}/transitions',
            json_body={'target_state': 'IN_PROGRESS', 'expected_version': version, 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )

    blocked = _try_advance()
    _assert(blocked.status_code == 409, f'transição sem aprovação retornou HTTP {blocked.status_code}')
    state_after_block = _read_operations(database_url, case_id)
    _assert(state_after_block['state'] == 'PENDING_APPROVAL', 'bloqueio alterou o estado do caso')
    _assert(state_after_block['version'] == version, 'bloqueio alterou a versão do caso')
    negative_controls['transition_without_approval'] = 'passed'

    rejected = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/approvals',
            json_body={'approver': 'gestor-1', 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )['approval']

    blocked_pending = _try_advance()
    _assert(
        blocked_pending.status_code == 409,
        f'aprovação apenas PENDING liberou transição: HTTP {blocked_pending.status_code}',
    )
    negative_controls['transition_with_pending_approval'] = 'passed'

    rejection = _data(
        _post(
            session,
            base + f"/v1/service-cases/{case_id}/approvals/{rejected['approval_id']}/decision",
            json_body={'decision': 'REJECTED', 'event_id': str(uuid4()), 'reason': 'fora da janela'},
            correlation_id=correlation_id,
        )
    )
    _assert(rejection['approval']['status'] == 'REJECTED', 'rejeição não foi persistida')

    blocked_rejected = _try_advance()
    _assert(
        blocked_rejected.status_code == 409,
        f'rejeição não manteve o bloqueio: HTTP {blocked_rejected.status_code}',
    )
    negative_controls['transition_after_rejection'] = 'passed'

    reopen = _post(
        session,
        base + f"/v1/service-cases/{case_id}/approvals/{rejected['approval_id']}/decision",
        json_body={'decision': 'APPROVED', 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(reopen.status_code == 422, f'decisão terminal foi reaberta: HTTP {reopen.status_code}')
    negative_controls['approval_decision_is_terminal'] = 'passed'

    approved = _data(
        _post(
            session,
            base + f'/v1/service-cases/{case_id}/approvals',
            json_body={'approver': 'gestor-2', 'event_id': str(uuid4())},
            correlation_id=correlation_id,
        )
    )['approval']
    decision_event = str(uuid4())
    decision_url = base + f"/v1/service-cases/{case_id}/approvals/{approved['approval_id']}/decision"
    decision = _data(
        _post(
            session,
            decision_url,
            json_body={'decision': 'APPROVED', 'event_id': decision_event},
            correlation_id=correlation_id,
        )
    )
    _assert(decision['duplicate'] is False, 'primeira decisão marcada como duplicada')

    decision_replay = _data(
        _post(
            session,
            decision_url,
            json_body={'decision': 'APPROVED', 'event_id': decision_event},
            correlation_id=correlation_id,
        )
    )
    _assert(decision_replay['duplicate'] is True, 'replay de decisão não foi idempotente')

    released = _try_advance()
    _assert(released.status_code == 200, f'aprovação válida não liberou transição: HTTP {released.status_code}')
    _assert(
        released.json()['data']['case']['state'] == 'IN_PROGRESS',
        'transição liberada não persistiu IN_PROGRESS',
    )

    # --- leitura independente final e histórico append-only ---------------
    final = _read_operations(database_url, case_id)
    _assert(final['state'] == 'IN_PROGRESS', 'estado final divergente na leitura independente')
    _assert(
        [item['status'] for item in final['approvals']] == ['REJECTED', 'APPROVED'],
        f"histórico de aprovações divergente: {final['approvals']}",
    )
    _assert(
        final['approvals'][0]['decision_reason'] == 'fora da janela',
        'motivo da rejeição não foi preservado',
    )
    _assert(
        final['event_counts'].get('APPROVAL_DECIDED') == 2,
        f"eventos de decisão divergentes: {final['event_counts']}",
    )
    _assert(
        final['event_counts'].get('APPROVAL_REQUESTED') == 2,
        f"eventos de solicitação divergentes: {final['event_counts']}",
    )
    _assert(
        final['event_counts'].get('ASSIGNMENT_CHANGED') == 2,
        f"eventos de atribuição divergentes: {final['event_counts']}",
    )
    _assert(final['event_counts'].get('SLA_APPLIED') == 1, 'evento de SLA duplicado')
    _assert(len(final['assignments']) == 2, 'histórico de atribuição alterado ao final')

    api_view = _data(session.get(base + f'/v1/service-cases/{case_id}/operations', timeout=20))
    _assert(api_view['state'] == final['state'], 'API e leitura independente divergem no estado')
    _assert(
        api_view['current_assignment']['assignment_group'] == 'Engenharia',
        'atribuição corrente divergente na API',
    )
    _assert(
        api_view['sla']['first_response_at'] is not None,
        'primeira resposta não foi derivada do histórico',
    )

    # --- teste do teste ---------------------------------------------------
    unknown_case = _post(
        session,
        base + f'/v1/service-cases/{uuid4()}/assignments',
        json_body={'assignment_group': 'Sustentacao', 'event_id': str(uuid4())},
        correlation_id=correlation_id,
    )
    _assert(
        unknown_case.status_code == 404,
        f'teste do teste não detectou caso inexistente: {unknown_case.status_code}',
    )

    return {
        'status': 'passed',
        'increment': 'RSM-04',
        'environment': build_info.get('environment'),
        'sha': runtime_sha,
        'expected_sha': expected_sha,
        'correlation_id': correlation_id,
        'service_id': service_id,
        'case_id': case_id,
        'policy_id': policy_id,
        'policy_code': policy_code,
        'priority': priority,
        'sla_factor': factor,
        'expected': (
            'SLA determinístico persistido, atribuição auditada, portão de aprovação '
            'fail-closed e histórico append-only confirmado por leitura independente'
        ),
        'observed': {
            'sla': {
                'priority': final['sla']['priority'],
                'started_at': final['sla']['started_at'],
                'response_due_at': final['sla']['response_due_at'],
                'resolution_due_at': final['sla']['resolution_due_at'],
            },
            'assignments': final['assignments'],
            'approvals': final['approvals'],
            'event_counts': final['event_counts'],
            'state': final['state'],
            'version': final['version'],
        },
        'independent_readback': 'postgresql',
        'sla_determinism': sla_determinism,
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
