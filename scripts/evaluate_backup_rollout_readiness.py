#!/usr/bin/env python3
"""Validate immutable backup evidence and decide governed rollout eligibility."""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
TARGET_BY_SOURCE = {"dev": "stg", "stg": "prod"}


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _base_report(
    *,
    source_environment: str,
    source_run_id: str,
    source_artifact_digest: str,
    decision: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.1.0",
        "control_id": "BACEN-04",
        "contract": "reqsys-backup-rollout-readiness",
        "source_environment": source_environment,
        "target_environment": TARGET_BY_SOURCE[source_environment],
        "decision": decision,
        "stg_allowed": False,
        "prod_allowed": False,
        "human_prod_approval_required": source_environment == "stg",
        "automatic_prod_enable_allowed": False,
        "checks": [],
        "source_run_id": source_run_id,
        "source_artifact_digest": source_artifact_digest,
        "production_touched": False,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def evaluate(
    evidence: dict[str, Any] | None,
    *,
    source_run_id: str,
    source_artifact_digest: str,
    source_environment: str = "dev",
) -> dict[str, Any]:
    if source_environment not in TARGET_BY_SOURCE:
        raise ValueError(f"unsupported source environment: {source_environment}")

    if evidence is None:
        return _base_report(
            source_environment=source_environment,
            source_run_id=source_run_id,
            source_artifact_digest=source_artifact_digest,
            decision=f"blocked_missing_{source_environment}_evidence",
        )

    checks: list[dict[str, Any]] = []
    source = evidence.get("source_manifest") or {}
    restored = evidence.get("restored_manifest") or {}
    quota = evidence.get("quota") or {}

    _check(checks, "control_id", evidence.get("control_id") == "BACEN-04", str(evidence.get("control_id")))
    _check(
        checks,
        f"environment_{source_environment}",
        evidence.get("environment") == source_environment,
        str(evidence.get("environment")),
    )
    _check(
        checks,
        "artifact_digest_sha256_valid",
        bool(ARTIFACT_DIGEST_RE.fullmatch(source_artifact_digest)),
        "valid" if ARTIFACT_DIGEST_RE.fullmatch(source_artifact_digest) else "invalid",
    )
    _check(checks, "result_passed", evidence.get("result") == "passed", str(evidence.get("result")))
    _check(checks, "integrity_match", evidence.get("integrity_match") is True, str(evidence.get("integrity_match")))
    _check(checks, "source_quick_check", source.get("quick_check") == "ok", str(source.get("quick_check")))
    _check(checks, "restored_quick_check", restored.get("quick_check") == "ok", str(restored.get("quick_check")))

    source_sha = str(source.get("sha256") or "")
    restored_sha = str(restored.get("sha256") or "")
    _check(
        checks,
        "source_sha256_valid",
        bool(SHA256_RE.fullmatch(source_sha)),
        "valid" if SHA256_RE.fullmatch(source_sha) else "invalid",
    )
    _check(
        checks,
        "restored_sha256_valid",
        bool(SHA256_RE.fullmatch(restored_sha)),
        "valid" if SHA256_RE.fullmatch(restored_sha) else "invalid",
    )
    _check(
        checks,
        "sha256_equal",
        bool(source_sha) and source_sha == restored_sha,
        "equal" if source_sha == restored_sha else "different",
    )
    _check(
        checks,
        "table_counts_digest_equal",
        bool(source.get("table_counts_sha256"))
        and source.get("table_counts_sha256") == restored.get("table_counts_sha256"),
        "equal" if source.get("table_counts_sha256") == restored.get("table_counts_sha256") else "different",
    )

    rpo = evidence.get("rpo_minutes")
    rpo_target = evidence.get("rpo_target_minutes")
    rto = evidence.get("rto_seconds")
    rto_target = evidence.get("rto_target_seconds")
    _check(
        checks,
        "rpo_within_target",
        isinstance(rpo, (int, float))
        and isinstance(rpo_target, (int, float))
        and rpo <= rpo_target,
        f"{rpo}/{rpo_target}",
    )
    _check(
        checks,
        "rto_within_target",
        isinstance(rto, (int, float))
        and isinstance(rto_target, (int, float))
        and rto <= rto_target,
        f"{rto}/{rto_target}",
    )
    _check(checks, "quota_healthy", quota.get("status") == "healthy", str(quota.get("status")))
    _check(
        checks,
        "production_read_only_false",
        evidence.get("production_read_only") is False,
        str(evidence.get("production_read_only")),
    )
    _check(
        checks,
        "production_restore_not_claimed",
        evidence.get("production_restore_claimed") is False,
        str(evidence.get("production_restore_claimed")),
    )
    _check(
        checks,
        "snapshot_present",
        bool(evidence.get("snapshot_id")),
        "present" if evidence.get("snapshot_id") else "missing",
    )
    _check(
        checks,
        "correlation_present",
        bool(evidence.get("correlation_id")),
        "present" if evidence.get("correlation_id") else "missing",
    )
    _check(
        checks,
        "run_url_https",
        str(evidence.get("run_url") or "").startswith("https://github.com/"),
        str(evidence.get("run_url") or ""),
    )

    allowed = all(item["passed"] for item in checks)
    if source_environment == "dev":
        decision = "stg_rollout_candidate" if allowed else "blocked_invalid_dev_evidence"
        stg_allowed = allowed
        prod_allowed = False
    else:
        decision = "prod_rollout_candidate_requires_approval" if allowed else "blocked_invalid_stg_evidence"
        stg_allowed = False
        prod_allowed = allowed

    report = _base_report(
        source_environment=source_environment,
        source_run_id=source_run_id,
        source_artifact_digest=source_artifact_digest,
        decision=decision,
    )
    report.update(
        {
            "stg_allowed": stg_allowed,
            "prod_allowed": prod_allowed,
            "checks": checks,
            "source_snapshot_id": evidence.get("snapshot_id"),
            "source_correlation_id": evidence.get("correlation_id"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-artifact-digest", default="")
    parser.add_argument("--source-environment", choices=sorted(TARGET_BY_SOURCE), default="dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    evidence = None
    if args.evidence and args.evidence.is_file():
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("evidence must be a JSON object")
        evidence = data

    report = evaluate(
        evidence,
        source_run_id=args.source_run_id,
        source_artifact_digest=args.source_artifact_digest,
        source_environment=args.source_environment,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [item["name"] for item in report["checks"] if not item["passed"]]
    print(f"backup rollout readiness: decision={report['decision']} failed={','.join(failed) or 'none'}")

    eligible_field = "stg_allowed" if args.source_environment == "dev" else "prod_allowed"
    return 1 if args.strict and not report[eligible_field] else 0


if __name__ == "__main__":
    raise SystemExit(main())
