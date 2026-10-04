#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}


def _load_list(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} deve conter uma lista JSON")
    return [item for item in value if isinstance(item, dict)]


def _sha_matches(left: Any, right: Any) -> bool:
    left_value = str(left or "").strip().lower()
    right_value = str(right or "").strip().lower()
    return bool(left_value and right_value) and (
        left_value.startswith(right_value) or right_value.startswith(left_value)
    )


def _runtime_valid(item: dict[str, Any]) -> bool:
    return (
        item.get("contract") == "reqsys-runtime-environment-evidence"
        and item.get("evidence_source") == "runtime"
        and item.get("attestation_provider") == "github-artifact-attestations"
        and item.get("environment") in ALLOWED_ENVIRONMENTS
        and item.get("blocking_issues") in ([], None)
        and bool(item.get("evidence_sha256"))
    )


def _ux_valid(item: dict[str, Any]) -> bool:
    return (
        item.get("evidence_source") == "runtime"
        and item.get("environment") in ALLOWED_ENVIRONMENTS
        and isinstance(item.get("recovery_rate"), (int, float))
        and isinstance(item.get("average_recovery_seconds"), (int, float))
        and isinstance(item.get("ux_100_ready"), bool)
    )


def build_single_state(
    runtime_ledger: list[dict[str, Any]],
    ux_chain: list[dict[str, Any]],
) -> dict[str, Any]:
    runtime_entries = [item for item in runtime_ledger if _runtime_valid(item)]
    ux_entries = [item for item in ux_chain if _ux_valid(item)]

    matches: list[dict[str, Any]] = []
    for runtime in runtime_entries:
        for ux in ux_entries:
            same_run = str(runtime.get("source_run_id")) == str(ux.get("source_run_id"))
            same_environment = runtime.get("environment") == ux.get("environment")
            same_sha = _sha_matches(runtime.get("observed_sha"), ux.get("source_head_sha"))
            if same_run and same_environment and same_sha:
                matches.append({"runtime": runtime, "ux": ux})

    latest = matches[-1] if matches else None
    production_ready = bool(
        latest
        and latest["runtime"].get("environment") == "prod"
        and latest["ux"].get("ux_100_ready") is True
        and latest["ux"].get("recovery_rate", 0) >= 80
        and latest["ux"].get("average_recovery_seconds", 999999) <= 30
    )

    status = "RUNTIME_UX_EVIDENCE_VERIFIED" if latest else "RUNTIME_UX_CORRELATION_PENDING"
    decision = {
        "status": status,
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "production_ready_candidate": production_ready,
        "promotion_allowed": False,
        "reason": (
            "runtime atestado e telemetria UX correlacionados por run, ambiente e SHA"
            if latest
            else "nenhum par de runtime atestado e UX real possui run, ambiente e SHA coincidentes"
        ),
    }

    evidence: dict[str, Any] | None = None
    if latest:
        runtime = latest["runtime"]
        ux = latest["ux"]
        evidence = {
            "environment": runtime["environment"],
            "source_run_id": str(runtime["source_run_id"]),
            "source_head_sha": ux["source_head_sha"],
            "observed_sha": runtime["observed_sha"],
            "correlation_id": runtime.get("correlation_id"),
            "attestation_provider": runtime["attestation_provider"],
            "evidence_sha256": runtime["evidence_sha256"],
            "recovery_rate": float(ux["recovery_rate"]),
            "average_recovery_seconds": float(ux["average_recovery_seconds"]),
            "ux_100_ready": ux["ux_100_ready"],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "reqsys-single-state-runtime-ux",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_evidence_count": len(runtime_entries),
        "ux_runtime_evidence_count": len(ux_entries),
        "correlated_evidence_count": len(matches),
        "decision": decision,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-ledger", required=True, type=Path)
    parser.add_argument("--ux-chain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build_single_state(
        _load_list(args.runtime_ledger),
        _load_list(args.ux_chain),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["decision"]["status"], "matches": result["correlated_evidence_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
