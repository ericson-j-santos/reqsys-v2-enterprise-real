#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERIFIED = "E2E_CORRELATION_VERIFIED"
PENDING = "E2E_CORRELATION_PENDING"


def build_indicator(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("contract") != "reqsys-runtime-ux-single-state-e2e-gate":
        raise ValueError("contrato E2E não autorizado")

    status = str(value.get("status") or PENDING)
    verified = status == VERIFIED
    checks = value.get("checks") if isinstance(value.get("checks"), dict) else {}

    guardrails_ok = (
        value.get("mode") == "advisory"
        and value.get("production_blocker") is False
        and value.get("promotion_allowed") is False
        and value.get("human_approval_required") is True
    )
    if not guardrails_ok:
        raise ValueError("guardrails de produção foram relaxados")

    required_checks = (
        "contract_valid",
        "guardrails_preserved",
        "correlation_verified",
        "environment_valid",
        "run_identity_present",
        "sha_consistent",
    )
    complete = verified and all(checks.get(name) is True for name in required_checks)
    if verified and not complete:
        raise ValueError("E2E_CORRELATION_VERIFIED sem checks completos")

    confidence_score = 100 if complete else 60
    production_readiness_score = 95 if complete and value.get("production_ready_candidate") else 75 if complete else 55
    operational_risk = "low" if complete else "medium"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state-e2e-executive-indicator",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_indicator": VERIFIED if complete else PENDING,
        "evidence_accepted": complete,
        "confidence": {
            "score": confidence_score,
            "level": "high" if complete else "medium",
            "basis": "verified_e2e_runtime_homologation_ux_identity" if complete else "correlation_pending",
        },
        "production_readiness": {
            "score": production_readiness_score,
            "candidate": bool(complete and value.get("production_ready_candidate")),
            "promotion_allowed": False,
            "human_approval_required": True,
        },
        "operational_risk": operational_risk,
        "checks": {name: bool(checks.get(name)) for name in required_checks},
        "source": {
            "contract": value.get("contract"),
            "status": status,
        },
        "mode": "advisory",
        "production_blocker": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2e", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    value = json.loads(args.e2e.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("e2e deve conter objeto JSON")
    result = build_indicator(value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"official_indicator": result["official_indicator"], "confidence": result["confidence"]["score"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
