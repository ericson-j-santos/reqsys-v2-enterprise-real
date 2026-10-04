#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}
ALLOWED_ORIGINS = {"integrated-runtime", "post-merge-smoke", "environment-homologation"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CORRELATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def build_metadata(*, environment: str, correlation_id: str, merge_sha: str, origin: str, generated_at: str | None = None) -> dict:
    environment = environment.strip().lower()
    origin = origin.strip().lower()
    merge_sha = merge_sha.strip().lower()
    correlation_id = correlation_id.strip()

    errors: list[str] = []
    if environment not in ALLOWED_ENVIRONMENTS:
        errors.append("invalid_environment")
    if origin not in ALLOWED_ORIGINS:
        errors.append("invalid_origin")
    if not SHA_RE.fullmatch(merge_sha):
        errors.append("invalid_merge_sha")
    if not CORRELATION_RE.fullmatch(correlation_id):
        errors.append("invalid_correlation_id")

    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("invalid_generated_at")

    return {
        "schema_version": "1.0",
        "evidence_source": "runtime" if not errors else "unverified",
        "verification_status": "verified" if not errors else "rejected",
        "origin": origin,
        "environment": environment,
        "generated_at": timestamp,
        "correlation_id": correlation_id,
        "merge_sha": merge_sha,
        "production_blocker": False,
        "human_approval_required": True,
        "validation_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--merge-sha", required=True)
    parser.add_argument("--origin", default="post-merge-smoke")
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    metadata = build_metadata(
        environment=args.environment,
        correlation_id=args.correlation_id,
        merge_sha=args.merge_sha,
        origin=args.origin,
        generated_at=args.generated_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if metadata["verification_status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
