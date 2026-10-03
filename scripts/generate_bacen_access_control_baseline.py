#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PROD_ALIASES = {"production", "prod", "prd"}
REQUIRED_JWT_KEYS = {"JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE", "JWT_EXP_MINUTES"}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera baseline técnico BACEN-02")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    env = parse_env(args.env_file)
    app_env = env.get("APP_ENV", "").lower()
    allow_demo = env.get("ALLOW_DEMO_LOGIN", "").lower() == "true"
    missing_jwt = sorted(key for key in REQUIRED_JWT_KEYS if not env.get(key))
    production_demo_violation = app_env in PROD_ALIASES and allow_demo

    findings: list[str] = []
    if missing_jwt:
        findings.append(f"missing_jwt_configuration:{','.join(missing_jwt)}")
    if production_demo_violation:
        findings.append("demo_login_enabled_in_production")

    source_bytes = args.env_file.read_bytes()
    technical_passed = not missing_jwt and not production_demo_violation
    evidence = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.env_file),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "environment_profile": app_env or "unknown",
        "jwt_configuration_present": not missing_jwt,
        "demo_login_policy_valid": not production_demo_violation,
        "mfa_evidence_status": "not_evidenced_in_repository",
        "quarterly_access_review_status": "not_evidenced_in_repository",
        "technical_baseline_passed": technical_passed,
        "control_maturity": "partial_pending_mfa_and_access_review_evidence",
        "production_touched": False,
        "findings": findings,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if technical_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
