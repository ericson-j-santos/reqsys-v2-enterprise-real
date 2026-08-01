#!/usr/bin/env python3
"""Evaluate backup provider readiness without exposing secret values."""
from __future__ import annotations
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

ALLOWED_PROBE_RESULTS = {"pass", "fail", "skipped"}
DEFAULT_REQUIRED_SECRETS = (
    "FLY_API_TOKEN",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "RESTIC_PASSWORD",
)

def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({item.strip() for item in value.split(",") if item.strip()})

def evaluate(*, required_secrets: Iterable[str], present_secrets: Iterable[str],
             fly_probe: str, r2_probe: str, restic_probe: str, run_url: str) -> dict:
    probes = {"fly": fly_probe, "r2_bucket": r2_probe, "restic_repository": restic_probe}
    invalid = sorted(name for name, result in probes.items() if result not in ALLOWED_PROBE_RESULTS)
    if invalid:
        raise ValueError(f"invalid probe results: {', '.join(invalid)}")
    required = sorted(set(required_secrets))
    present = sorted(set(present_secrets))
    missing = sorted(set(required) - set(present))
    if missing:
        decision = "blocked_configuration"
    elif any(result == "fail" for result in probes.values()):
        decision = "blocked_credentials_or_repository"
    elif all(result == "pass" for result in probes.values()):
        decision = "ready"
    else:
        decision = "probe_pending"
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "contract": "reqsys-backup-provider-readiness",
        "decision": decision,
        "ready": decision == "ready",
        "required_secret_names": required,
        "present_secret_names": present,
        "missing_secret_names": missing,
        "probes": probes,
        "secret_values_persisted": False,
        "production_touched": False,
        "run_url": run_url,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required", default=",".join(DEFAULT_REQUIRED_SECRETS))
    parser.add_argument("--present", default="")
    parser.add_argument("--fly-probe", choices=sorted(ALLOWED_PROBE_RESULTS), required=True)
    parser.add_argument("--r2-probe", choices=sorted(ALLOWED_PROBE_RESULTS), required=True)
    parser.add_argument("--restic-probe", choices=sorted(ALLOWED_PROBE_RESULTS), required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(
        required_secrets=_csv(args.required),
        present_secrets=_csv(args.present),
        fly_probe=args.fly_probe,
        r2_probe=args.r2_probe,
        restic_probe=args.restic_probe,
        run_url=args.run_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"backup provider readiness: decision={report['decision']} missing={len(report['missing_secret_names'])}")
    return 1 if args.strict and not report["ready"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
