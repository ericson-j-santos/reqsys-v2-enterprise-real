#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}


def _sha_matches(left: Any, right: Any) -> bool:
    a = str(left or "").strip().lower()
    b = str(right or "").strip().lower()
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def validate_single_state(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("contract") != "reqsys-single-state-runtime-ux":
        raise ValueError("contrato do Estado Único não autorizado")

    decision = value.get("decision")
    evidence = value.get("evidence")
    if not isinstance(decision, dict):
        raise ValueError("decision ausente")

    if decision.get("mode") != "advisory":
        raise ValueError("modo deve permanecer advisory")
    if decision.get("production_blocker") is not False:
        raise ValueError("production_blocker deve permanecer false")
    if decision.get("promotion_allowed") is not False:
        raise ValueError("promotion_allowed deve permanecer false")
    if decision.get("human_approval_required") is not True:
        raise ValueError("aprovação humana deve permanecer obrigatória")

    verified = decision.get("status") == "RUNTIME_UX_EVIDENCE_VERIFIED"
    checks = {
        "contract_valid": True,
        "guardrails_preserved": True,
        "correlation_verified": False,
        "environment_valid": False,
        "run_identity_present": False,
        "sha_consistent": False,
    }

    if verified:
        if not isinstance(evidence, dict):
            raise ValueError("estado verificado exige evidence")
        environment = evidence.get("environment")
        source_run_id = str(evidence.get("source_run_id") or "").strip()
        source_head_sha = evidence.get("source_head_sha")
        observed_sha = evidence.get("observed_sha")

        checks["environment_valid"] = environment in ALLOWED_ENVIRONMENTS
        checks["run_identity_present"] = bool(source_run_id)
        checks["sha_consistent"] = _sha_matches(source_head_sha, observed_sha)
        checks["correlation_verified"] = all(
            checks[key]
            for key in ("environment_valid", "run_identity_present", "sha_consistent")
        )
        if not checks["correlation_verified"]:
            raise ValueError("correlação declarada como verificada sem identidade completa")

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-runtime-ux-single-state-e2e-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "E2E_CORRELATION_VERIFIED" if checks["correlation_verified"] else "E2E_CORRELATION_PENDING",
        "checks": checks,
        "source_status": decision.get("status"),
        "production_ready_candidate": bool(decision.get("production_ready_candidate")),
        "promotion_allowed": False,
        "human_approval_required": True,
        "production_blocker": False,
        "mode": "advisory",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    value = json.loads(args.single_state.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("single-state deve conter objeto JSON")
    result = validate_single_state(value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
