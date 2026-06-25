"""Validador CI do contrato governado de observabilidade.

Uso:
    python scripts/validate_observability_contract.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.telemetry_contract import (  # noqa: E402
    build_evidence_index,
    sample_valid_event,
    validate_telemetry_event,
)


def main() -> int:
    event = sample_valid_event()
    result = validate_telemetry_event(event)
    if not result.valid:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 1

    invalid_event = dict(event)
    invalid_event.pop("trace_id")
    invalid_result = validate_telemetry_event(invalid_event)
    if invalid_result.valid:
        print("Contrato falhou: evento sem trace_id foi aceito.")
        return 1

    evidence = build_evidence_index()
    required_flags = (
        "telemetry_contract",
        "runtime_health",
        "evidence_index",
        "drift_analytics",
        "ci_contract_gate",
    )
    missing = [flag for flag in required_flags if not evidence["coverage"].get(flag)]
    if missing:
        print(f"Índice de evidências incompleto: {missing}")
        return 1

    print(json.dumps({
        "status": "ok",
        "increment": evidence["increment"],
        "domain": evidence["domain"],
        "validated_event": event["event_name"],
        "ci_gate": "observability-contract",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
