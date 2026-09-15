#!/usr/bin/env python3
"""Resolve a fonte de evidência de runtime sem fallback silencioso.

DEV pode usar Fly (transição) ou PC24x7. STG/PROD permanecem Fly. Quando DEV
solicita PC24x7, a evidência local precisa existir, estar pronta, corresponder
ao SHA esperado e estar dentro da janela de frescor.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VALID_ENVIRONMENTS = {"dev", "stg", "prod"}
VALID_PROVIDERS = {"fly", "pc24x7"}
DEFAULT_MAX_AGE_SECONDS = 900


def _parse_timestamp(raw: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_pc24x7_evidence(
    evidence: dict[str, Any],
    *,
    expected_sha: str,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if evidence.get("contract") != "pc24x7-dev-runtime-evidence":
        findings.append("invalid_contract")
    if evidence.get("provider") != "pc24x7":
        findings.append("invalid_provider")
    if evidence.get("environment") != "dev":
        findings.append("invalid_environment")
    if evidence.get("ready") is not True or evidence.get("runtime_ready") is not True:
        findings.append("runtime_not_ready")
    if evidence.get("source_commit") != expected_sha:
        findings.append("source_commit_mismatch")

    generated_at = _parse_timestamp(evidence.get("generated_at"))
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    reference = reference.astimezone(UTC)
    if generated_at is None:
        findings.append("invalid_generated_at")
    else:
        age_seconds = (reference - generated_at).total_seconds()
        if age_seconds < -60:
            findings.append("evidence_from_future")
        if age_seconds > max_age_seconds:
            findings.append("evidence_stale")

    return not findings, findings


def resolve_provider(
    environment: str,
    requested_provider: str,
    *,
    expected_sha: str,
    evidence: dict[str, Any] | None = None,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"ambiente inválido: {environment}")
    if requested_provider not in VALID_PROVIDERS:
        raise ValueError(f"provedor inválido: {requested_provider}")

    if environment != "dev":
        if requested_provider != "fly":
            return {
                "allowed": False,
                "environment": environment,
                "provider": requested_provider,
                "findings": ["pc24x7_not_allowed_outside_dev"],
            }
        return {
            "allowed": True,
            "environment": environment,
            "provider": "fly",
            "findings": [],
        }

    if requested_provider == "fly":
        return {
            "allowed": True,
            "environment": "dev",
            "provider": "fly",
            "findings": ["transitional_fly_provider"],
        }

    if evidence is None:
        return {
            "allowed": False,
            "environment": "dev",
            "provider": "pc24x7",
            "findings": ["pc24x7_evidence_missing"],
        }

    valid, findings = validate_pc24x7_evidence(
        evidence,
        expected_sha=expected_sha,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    return {
        "allowed": valid,
        "environment": "dev",
        "provider": "pc24x7",
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve provedor de evidência de runtime")
    parser.add_argument("--environment", choices=sorted(VALID_ENVIRONMENTS), required=True)
    parser.add_argument("--provider", choices=sorted(VALID_PROVIDERS), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--pc24x7-evidence", type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    args = parser.parse_args()

    evidence = None
    if args.pc24x7_evidence is not None:
        if not args.pc24x7_evidence.exists():
            result = {
                "allowed": False,
                "environment": args.environment,
                "provider": args.provider,
                "findings": ["pc24x7_evidence_file_not_found"],
            }
            print(json.dumps(result, ensure_ascii=False))
            return 1
        evidence = json.loads(args.pc24x7_evidence.read_text(encoding="utf-8"))

    result = resolve_provider(
        args.environment,
        args.provider,
        expected_sha=args.expected_sha,
        evidence=evidence,
        max_age_seconds=args.max_age_seconds,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
