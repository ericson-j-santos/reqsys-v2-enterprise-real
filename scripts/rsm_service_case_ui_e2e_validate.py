#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg2


def _sql_url(value: str) -> str:
    return value.replace("postgresql+psycopg2://", "postgresql://", 1)


def _read_case(cur, key: str) -> dict:
    cur.execute(
        "SELECT case_id, state, version, correlation_id "
        "FROM rsm_service_cases WHERE idempotency_key = %s",
        (key,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("ServiceCase ausente na leitura PostgreSQL independente")
    cur.execute(
        "SELECT event_type, from_state, to_state "
        "FROM rsm_service_case_events WHERE case_id = %s "
        "ORDER BY created_at, event_id",
        (row[0],),
    )
    events = [
        {"event_type": item[0], "from_state": item[1], "to_state": item[2]}
        for item in cur.fetchall()
    ]
    return {
        "case_id": row[0],
        "state": row[1],
        "version": int(row[2]),
        "correlation_id": row[3],
        "events": events,
    }


def run(database_url: str, evidence_path: Path, expected_sha: str) -> dict:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("status") != "browser_passed":
        raise RuntimeError("evidência de browser não está verde")
    if evidence.get("expected_sha") != expected_sha:
        raise RuntimeError("evidência de browser pertence a outro SHA")

    with psycopg2.connect(_sql_url(database_url)) as conn:
        with conn.cursor() as cur:
            positive = _read_case(cur, evidence["positive"]["idempotency_key"])
            negative = _read_case(cur, evidence["negative"]["idempotency_key"])

    if positive["case_id"] != evidence["positive"]["case_id"]:
        raise RuntimeError("case_id positivo divergiu na leitura PostgreSQL")
    if positive["state"] != "TRIAGE" or positive["version"] != 2:
        raise RuntimeError(
            f"positivo inesperado: state={positive['state']} version={positive['version']}"
        )
    if [item["to_state"] for item in positive["events"]] != ["NEW", "TRIAGE"]:
        raise RuntimeError("histórico positivo não confirma NEW -> TRIAGE")

    if negative["case_id"] != evidence["negative"]["case_id"]:
        raise RuntimeError("case_id negativo divergiu na leitura PostgreSQL")
    if negative["state"] != "PENDING_APPROVAL" or negative["version"] != 3:
        raise RuntimeError(
            f"controle negativo alterou estado: state={negative['state']} version={negative['version']}"
        )
    if any(item["to_state"] == "IN_PROGRESS" for item in negative["events"]):
        raise RuntimeError("controle negativo persistiu transição IN_PROGRESS indevida")
    if [item["to_state"] for item in negative["events"]] != [
        "NEW",
        "TRIAGE",
        "PENDING_APPROVAL",
    ]:
        raise RuntimeError("histórico negativo divergiu do esperado")

    evidence.update(
        {
            "status": "passed",
            "independent_readback": "postgresql",
            "positive_control": "passed",
            "negative_control": "passed",
            "false_success_guard": "passed",
            "observed": {
                "positive": positive,
                "negative": negative,
            },
        }
    )
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args.database_url, args.evidence, args.expected_sha)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__, "detail": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
