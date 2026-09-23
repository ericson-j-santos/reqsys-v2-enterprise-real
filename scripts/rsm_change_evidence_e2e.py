#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import requests


def _sql_url(value: str) -> str:
    return value.replace("postgresql+psycopg2://", "postgresql://", 1)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _data(response: requests.Response) -> dict:
    response.raise_for_status()
    return response.json()["data"]


def _post(
    session: requests.Session,
    url: str,
    *,
    json_body: dict,
    correlation_id: str,
) -> requests.Response:
    return session.post(
        url,
        json=json_body,
        headers={"X-Correlation-ID": correlation_id},
        timeout=20,
    )


def _active_service(database_url: str) -> str:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT servico_id FROM gestao_ti_servicos "
                "WHERE ativo = true ORDER BY codigo LIMIT 1"
            )
            row = cur.fetchone()
            _assert(row is not None, "nenhum ServicoTI ativo disponível para o E2E")
            return str(row[0])


def _readback(database_url: str, case_id: str) -> dict:
    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state, version FROM rsm_service_cases WHERE case_id = %s",
                (case_id,),
            )
            case = cur.fetchone()
            _assert(case is not None, "CHANGE ausente na leitura independente")
            cur.execute(
                "SELECT COUNT(*), MAX(status), MAX(head_sha), MAX(runtime_sha) "
                "FROM rsm_change_execution_evidence WHERE case_id = %s",
                (case_id,),
            )
            evidence = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM rsm_service_case_events "
                "WHERE case_id = %s AND event_type = 'CHANGE_RUNTIME_EVIDENCE_RECORDED'",
                (case_id,),
            )
            event_count = int(cur.fetchone()[0])
            return {
                "state": case[0],
                "version": int(case[1]),
                "evidence_count": int(evidence[0]),
                "status": evidence[1],
                "head_sha": evidence[2],
                "runtime_sha": evidence[3],
                "evidence_event_count": event_count,
            }


def _transition(
    session: requests.Session,
    base_url: str,
    case: dict,
    target: str,
    *,
    correlation_id: str,
    evidence: bool = False,
) -> requests.Response:
    body = {
        "target_state": target,
        "expected_version": case["version"],
        "event_id": str(uuid4()),
    }
    if evidence:
        body["evidence_uri"] = f"urn:reqsys:rsm-07:resolution:{correlation_id}"
        body["evidence_sha256"] = _sha256(correlation_id + ":resolution")
    return _post(
        session,
        base_url.rstrip("/") + f"/v1/service-cases/{case['case_id']}/transitions",
        json_body=body,
        correlation_id=correlation_id,
    )


def run(base_url: str, database_url: str, expected_sha: str) -> dict:
    expected_sha = expected_sha.strip().lower()
    _assert(
        len(expected_sha) in {40, 64}
        and all(ch in "0123456789abcdef" for ch in expected_sha),
        "expected_sha deve ser SHA Git completo hexadecimal",
    )

    correlation_id = f"rsm07-{uuid4().hex}"
    idempotency_key = _sha256(f"rsm07-change-{uuid4().hex}")
    service_id = _active_service(database_url)
    session = requests.Session()

    login = session.post(
        base_url.rstrip("/") + "/v1/auth/login",
        json={"email": "rsm-e2e@example.com"},
        timeout=20,
    )
    login_data = _data(login)
    session.headers.update({"Authorization": f"Bearer {login_data['access_token']}"})

    build_info = _data(
        session.get(base_url.rstrip("/") + "/api/runtime/build-info", timeout=20)
    )
    runtime_build_sha = str(build_info.get("build_sha") or "").strip().lower()
    _assert(
        runtime_build_sha == expected_sha,
        f"build-info SHA divergente: esperado={expected_sha} observado={runtime_build_sha}",
    )

    created = _data(
        _post(
            session,
            base_url.rstrip("/") + "/v1/service-cases",
            json_body={
                "case_type": "CHANGE",
                "service_id": service_id,
                "requester": "rsm-07-e2e",
                "impact": "HIGH",
                "urgency": "HIGH",
                "idempotency_key": idempotency_key,
                "event_id": str(uuid4()),
                "source": "reqsys",
            },
            correlation_id=correlation_id,
        )
    )
    case = created["case"]
    _assert(created["duplicate"] is False, "primeira criação marcada como duplicada")

    for target in ("TRIAGE", "IN_PROGRESS"):
        response = _transition(
            session,
            base_url,
            case,
            target,
            correlation_id=correlation_id,
        )
        case = _data(response)["case"]

    resolved = _transition(
        session,
        base_url,
        case,
        "RESOLVED",
        correlation_id=correlation_id,
        evidence=True,
    )
    case = _data(resolved)["case"]
    _assert(case["state"] == "RESOLVED", "CHANGE não chegou a RESOLVED")

    blocked_close = _transition(
        session,
        base_url,
        case,
        "CLOSED",
        correlation_id=correlation_id,
    )
    _assert(
        blocked_close.status_code == 409,
        f"CLOSED sem runtime evidence retornou HTTP {blocked_close.status_code}",
    )
    before = _readback(database_url, case["case_id"])
    _assert(before["state"] == "RESOLVED", "bloqueio sem evidência alterou o estado")
    _assert(before["evidence_count"] == 0, "bloqueio sem evidência persistiu registro")

    wrong_sha_payload = {
        "event_id": str(uuid4()),
        "requirement_ref": "REQ-1789",
        "sdd_ref": "rsm-07-change-traceability",
        "pull_request_ref": "PR-RSM-07-E2E",
        "head_sha": expected_sha,
        "ci_run_id": "rsm-07-e2e-ci",
        "ci_conclusion": "success",
        "deployment_ref": f"github-actions:{expected_sha}",
        "environment": "ci-e2e",
        "runtime_sha": ("0" if expected_sha[0] != "0" else "1") + expected_sha[1:],
        "post_deploy_evidence_uri": f"urn:reqsys:rsm-07:{correlation_id}:wrong-sha",
        "post_deploy_evidence_sha256": _sha256(correlation_id + ":wrong-sha"),
        "status": "PASSED",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    wrong_sha = _post(
        session,
        base_url.rstrip("/") + f"/v1/service-cases/{case['case_id']}/change-evidence",
        json_body=wrong_sha_payload,
        correlation_id=correlation_id,
    )
    _assert(
        wrong_sha.status_code == 422,
        f"runtime SHA divergente retornou HTTP {wrong_sha.status_code}",
    )
    after_wrong = _readback(database_url, case["case_id"])
    _assert(
        after_wrong["evidence_count"] == 0,
        "runtime SHA divergente deixou evidência persistida",
    )

    evidence_event_id = str(uuid4())
    evidence_payload = {
        "event_id": evidence_event_id,
        "requirement_ref": "REQ-1789",
        "sdd_ref": "rsm-07-change-traceability",
        "pull_request_ref": "PR-RSM-07-E2E",
        "head_sha": expected_sha,
        "ci_run_id": "rsm-07-e2e-ci",
        "ci_conclusion": "success",
        "deployment_ref": f"github-actions:{expected_sha}",
        "environment": "ci-e2e",
        "runtime_sha": runtime_build_sha,
        "post_deploy_evidence_uri": f"urn:reqsys:rsm-07:{correlation_id}:post-deploy",
        "post_deploy_evidence_sha256": _sha256(correlation_id + ":post-deploy"),
        "status": "PASSED",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence_response = _post(
        session,
        base_url.rstrip("/") + f"/v1/service-cases/{case['case_id']}/change-evidence",
        json_body=evidence_payload,
        correlation_id=correlation_id,
    )
    evidence = _data(evidence_response)
    _assert(evidence["duplicate"] is False, "primeira evidência marcada como replay")

    replay = _data(
        _post(
            session,
            base_url.rstrip("/") + f"/v1/service-cases/{case['case_id']}/change-evidence",
            json_body=evidence_payload,
            correlation_id=correlation_id,
        )
    )
    _assert(replay["duplicate"] is True, "replay da evidência não convergiu")

    closed_response = _transition(
        session,
        base_url,
        case,
        "CLOSED",
        correlation_id=correlation_id,
    )
    case = _data(closed_response)["case"]
    _assert(case["state"] == "CLOSED", "CHANGE não chegou a CLOSED")

    terminal = _readback(database_url, case["case_id"])
    _assert(terminal["state"] == "CLOSED", "leitura independente não confirmou CLOSED")
    _assert(terminal["evidence_count"] == 1, "replay duplicou evidência")
    _assert(terminal["evidence_event_count"] == 1, "replay duplicou evento")
    _assert(terminal["status"] == "PASSED", "status persistido não é PASSED")
    _assert(terminal["head_sha"] == expected_sha, "head SHA persistido divergiu")
    _assert(terminal["runtime_sha"] == expected_sha, "runtime SHA persistido divergiu")

    return {
        "status": "passed",
        "environment": build_info.get("environment"),
        "sha": runtime_build_sha,
        "expected_sha": expected_sha,
        "correlation_id": correlation_id,
        "event_id": evidence_event_id,
        "idempotency_key": idempotency_key,
        "case_id": case["case_id"],
        "expected": (
            "CLOSED somente após runtime_sha == head_sha e evidência pós-deploy persistida"
        ),
        "observed": terminal,
        "positive": "passed",
        "negative_missing_evidence": "passed",
        "negative_sha_mismatch": "passed",
        "replay": "passed",
        "independent_readback": "postgresql",
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = run(args.base_url, args.database_url, args.expected_sha)
    except Exception as exc:
        evidence = {
            "status": "failed",
            "error": type(exc).__name__,
            "detail": str(exc)[:500],
        }
        code = 2
    else:
        code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
