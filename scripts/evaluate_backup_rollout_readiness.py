#!/usr/bin/env python3
"""Validate DEV backup evidence and decide whether STG rollout may be proposed."""
from __future__ import annotations
import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})

def evaluate(evidence: dict[str, Any] | None, *, source_run_id: str,
             source_artifact_digest: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if evidence is None:
        return {
            "schema_version": "1.0.0",
            "control_id": "BACEN-04",
            "contract": "reqsys-backup-rollout-readiness",
            "decision": "blocked_missing_dev_evidence",
            "stg_allowed": False,
            "prod_allowed": False,
            "automatic_prod_enable_allowed": False,
            "checks": [],
            "source_run_id": source_run_id,
            "source_artifact_digest": source_artifact_digest,
            "production_touched": False,
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }

    source = evidence.get("source_manifest") or {}
    restored = evidence.get("restored_manifest") or {}
    quota = evidence.get("quota") or {}

    _check(checks, "control_id", evidence.get("control_id") == "BACEN-04", str(evidence.get("control_id")))
    _check(checks, "environment_dev", evidence.get("environment") == "dev", str(evidence.get("environment")))
    _check(checks, "result_passed", evidence.get("result") == "passed", str(evidence.get("result")))
    _check(checks, "integrity_match", evidence.get("integrity_match") is True, str(evidence.get("integrity_match")))
    _check(checks, "source_quick_check", source.get("quick_check") == "ok", str(source.get("quick_check")))
    _check(checks, "restored_quick_check", restored.get("quick_check") == "ok", str(restored.get("quick_check")))
    source_sha = str(source.get("sha256") or "")
    restored_sha = str(restored.get("sha256") or "")
    _check(checks, "source_sha256_valid", bool(SHA256_RE.fullmatch(source_sha)),
           "valid" if SHA256_RE.fullmatch(source_sha) else "invalid")
    _check(checks, "restored_sha256_valid", bool(SHA256_RE.fullmatch(restored_sha)),
           "valid" if SHA256_RE.fullmatch(restored_sha) else "invalid")
    _check(checks, "sha256_equal", bool(source_sha) and source_sha == restored_sha,
           "equal" if source_sha == restored_sha else "different")
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
    _check(checks, "rpo_within_target",
           isinstance(rpo, (int, float)) and isinstance(rpo_target, (int, float)) and rpo <= rpo_target,
           f"{rpo}/{rpo_target}")
    _check(checks, "rto_within_target",
           isinstance(rto, (int, float)) and isinstance(rto_target, (int, float)) and rto <= rto_target,
           f"{rto}/{rto_target}")
    _check(checks, "quota_healthy", quota.get("status") == "healthy", str(quota.get("status")))
    _check(checks, "production_read_only_false", evidence.get("production_read_only") is False,
           str(evidence.get("production_read_only")))
    _check(checks, "production_restore_not_claimed",
           evidence.get("production_restore_claimed") is False,
           str(evidence.get("production_restore_claimed")))
    _check(checks, "snapshot_present", bool(evidence.get("snapshot_id")),
           "present" if evidence.get("snapshot_id") else "missing")
    _check(checks, "correlation_present", bool(evidence.get("correlation_id")),
           "present" if evidence.get("correlation_id") else "missing")
    _check(checks, "run_url_https",
           str(evidence.get("run_url") or "").startswith("https://github.com/"),
           str(evidence.get("run_url") or ""))

    stg_allowed = all(item["passed"] for item in checks)
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "contract": "reqsys-backup-rollout-readiness",
        "decision": "stg_rollout_candidate" if stg_allowed else "blocked_invalid_dev_evidence",
        "stg_allowed": stg_allowed,
        "prod_allowed": False,
        "automatic_prod_enable_allowed": False,
        "checks": checks,
        "source_run_id": source_run_id,
        "source_artifact_digest": source_artifact_digest,
        "source_snapshot_id": evidence.get("snapshot_id"),
        "source_correlation_id": evidence.get("correlation_id"),
        "production_touched": False,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-artifact-digest", default="")
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
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [item["name"] for item in report["checks"] if not item["passed"]]
    print(f"backup rollout readiness: decision={report['decision']} failed={','.join(failed) or 'none'}")
    return 1 if args.strict and not report["stg_allowed"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
