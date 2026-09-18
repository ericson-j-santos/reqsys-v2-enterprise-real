#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}
MAX_LEDGER_ENTRIES = 90


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_sha(value: Any) -> str:
    return str(value or "").strip().lower()


def _sha_matches(expected: str, observed: str) -> bool:
    expected = _normalize_sha(expected)
    observed = _normalize_sha(observed)
    return bool(expected and observed) and (
        expected.startswith(observed) or observed.startswith(expected)
    )


def build_record(
    evidence: dict[str, Any],
    *,
    evidence_bytes: bytes,
    source_run_id: str,
    source_head_sha: str,
    source_workflow: str,
) -> dict[str, Any]:
    if evidence.get("contract") != "fly-environment-homologation-gate":
        raise ValueError("contrato de evidência não autorizado")
    if evidence.get("ok") is not True:
        raise ValueError("ambiente não homologado")

    environment = str(evidence.get("environment") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("ambiente inválido")

    expected_sha = _normalize_sha(evidence.get("expected_sha"))
    observed_sha = _normalize_sha(evidence.get("observed_sha"))
    if not _sha_matches(expected_sha, observed_sha):
        raise ValueError("SHA observado não corresponde ao SHA esperado")
    if len(source_head_sha.strip()) < 7:
        raise ValueError("source_head_sha inválido")
    if not str(source_run_id).strip():
        raise ValueError("source_run_id obrigatório")

    generated_epoch = evidence.get("generated_at_epoch")
    if not isinstance(generated_epoch, int) or generated_epoch <= 0:
        raise ValueError("generated_at_epoch inválido")

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "reqsys-runtime-environment-evidence",
        "evidence_source": "runtime",
        "attestation_provider": "github-artifact-attestations",
        "environment": environment,
        "source_workflow": source_workflow,
        "source_run_id": str(source_run_id),
        "source_head_sha": source_head_sha,
        "expected_sha": expected_sha,
        "observed_sha": observed_sha,
        "correlation_id": evidence.get("correlation_id"),
        "base_url": evidence.get("base_url"),
        "fly_app": evidence.get("fly_app"),
        "observed_at": datetime.fromtimestamp(generated_epoch, timezone.utc).isoformat(),
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "probes_total": len(evidence.get("probes") or []),
        "blocking_issues": evidence.get("blocking_issues") or [],
        "production_blocker": False,
        "human_approval_required": environment == "prod",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def append_ledger(
    previous: list[dict[str, Any]], record: dict[str, Any]
) -> list[dict[str, Any]]:
    key = f"{record['source_run_id']}:{record['environment']}"
    indexed: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in [*previous, record]:
        item_key = f"{item.get('source_run_id')}:{item.get('environment')}"
        if item_key not in indexed:
            order.append(item_key)
        indexed[item_key] = item
    if key not in indexed:
        order.append(key)
        indexed[key] = record
    return [indexed[item_key] for item_key in order][-MAX_LEDGER_ENTRIES:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--previous-ledger", type=Path)
    parser.add_argument("--ledger-output", required=True, type=Path)
    args = parser.parse_args()

    evidence_bytes = args.evidence.read_bytes()
    evidence = json.loads(evidence_bytes.decode("utf-8"))
    if not isinstance(evidence, dict):
        raise ValueError("evidence deve conter objeto JSON")

    record = build_record(
        evidence,
        evidence_bytes=evidence_bytes,
        source_run_id=args.source_run_id,
        source_head_sha=args.source_head_sha,
        source_workflow=args.source_workflow,
    )

    previous: list[dict[str, Any]] = []
    if args.previous_ledger and args.previous_ledger.exists():
        value = _load_json(args.previous_ledger)
        if not isinstance(value, list):
            raise ValueError("ledger anterior deve conter lista JSON")
        previous = [item for item in value if isinstance(item, dict)]

    ledger = append_ledger(previous, record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.ledger_output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"environment": record["environment"], "ledger_entries": len(ledger)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
