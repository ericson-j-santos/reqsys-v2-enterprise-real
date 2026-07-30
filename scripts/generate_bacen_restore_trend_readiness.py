#!/usr/bin/env python3
"""Consolida tendência histórica BACEN-04 sem declarar restauração produtiva."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_GLOB = "artifacts/bacen/history/bacen-04-*.json"
DEFAULT_OUTPUT = "artifacts/bacen/bacen-04-restore-trend-readiness.json"
MIN_OPERATIONAL_SAMPLES = 3
MAX_EVIDENCE_AGE_DAYS = 120


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def parse_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} deve ser ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} deve conter timezone")
    return parsed


def percentile_nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[rank - 1]


def normalize_evidence(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path}: evidência deve ser objeto JSON")
    if document.get("control_id") != "BACEN-04":
        raise ValueError(f"{path}: control_id deve ser BACEN-04")
    if document.get("production_touched") is not False:
        raise ValueError(f"{path}: production_touched deve ser false")
    if document.get("production_restore_claimed") is not False:
        raise ValueError(f"{path}: production_restore_claimed deve ser false")

    rpo_minutes = document.get("rpo_minutes")
    if isinstance(rpo_minutes, bool) or not isinstance(rpo_minutes, (int, float)) or rpo_minutes < 0:
        raise ValueError(f"{path}: rpo_minutes inválido")

    if "rto_seconds" in document:
        rto_seconds = document["rto_seconds"]
    elif "rto_minutes" in document:
        rto_seconds = float(document["rto_minutes"]) * 60.0
    else:
        raise ValueError(f"{path}: rto_seconds ou rto_minutes obrigatório")
    if isinstance(rto_seconds, bool) or not isinstance(rto_seconds, (int, float)) or rto_seconds < 0:
        raise ValueError(f"{path}: RTO inválido")

    completed_at = parse_datetime(
        document.get("restore_completed_at") or document.get("generated_at"),
        f"{path}: restore_completed_at",
    )
    result = str(document.get("result") or "")
    if result not in {"passed", "failed"}:
        raise ValueError(f"{path}: result deve ser passed ou failed")

    rpo_target = float(document.get("rpo_target_minutes", 1440))
    rto_target = float(document.get("rto_target_seconds", 14400))
    target_met = result == "passed" and float(rpo_minutes) <= rpo_target and float(rto_seconds) <= rto_target
    return {
        "path": str(path),
        "evidence_class": str(document.get("evidence_class") or "unknown"),
        "completed_at": completed_at,
        "rpo_minutes": float(rpo_minutes),
        "rto_seconds": float(rto_seconds),
        "result": result,
        "target_met": target_met,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_trend(
    evidence_glob: str,
    output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    paths = [Path(item) for item in sorted(glob.glob(evidence_glob, recursive=True))]
    normalized = [normalize_evidence(path) for path in paths]
    operational = [
        item for item in normalized if item["evidence_class"] == "isolated_stg_restore_test"
    ]
    contract_only = len(normalized) - len(operational)

    if not operational:
        state = "pending_operational_history"
        result = "advisory"
        metrics = {
            "sample_count": 0,
            "pass_rate_percent": None,
            "median_rto_seconds": None,
            "p95_rto_seconds": None,
            "max_rpo_minutes": None,
            "latest_evidence_age_days": None,
        }
    else:
        rto_values = [float(item["rto_seconds"]) for item in operational]
        rpo_values = [float(item["rpo_minutes"]) for item in operational]
        target_met_count = sum(bool(item["target_met"]) for item in operational)
        latest = max(item["completed_at"] for item in operational)
        latest_age_days = round(max(0.0, (generated_at - latest).total_seconds() / 86400), 2)
        metrics = {
            "sample_count": len(operational),
            "pass_rate_percent": round(target_met_count / len(operational) * 100.0, 2),
            "median_rto_seconds": percentile_nearest_rank(rto_values, 50),
            "p95_rto_seconds": percentile_nearest_rank(rto_values, 95),
            "max_rpo_minutes": max(rpo_values),
            "latest_evidence_age_days": latest_age_days,
        }
        enough_samples = len(operational) >= MIN_OPERATIONAL_SAMPLES
        fresh = latest_age_days <= MAX_EVIDENCE_AGE_DAYS
        all_targets_met = target_met_count == len(operational)
        if enough_samples and fresh and all_targets_met:
            state = "trend_ready"
            result = "passed"
        elif not enough_samples:
            state = "insufficient_operational_history"
            result = "advisory"
        else:
            state = "trend_attention"
            result = "advisory"

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "evidence_class": "restore_trend_readiness",
        "source_glob": evidence_glob,
        "state": state,
        "result": result,
        "minimum_operational_samples": MIN_OPERATIONAL_SAMPLES,
        "maximum_evidence_age_days": MAX_EVIDENCE_AGE_DAYS,
        "discovered_files": len(normalized),
        "contract_only_files": contract_only,
        **metrics,
        "source_files": [
            {
                "path": item["path"],
                "evidence_class": item["evidence_class"],
                "result": item["result"],
                "target_met": item["target_met"],
                "source_sha256": item["source_sha256"],
            }
            for item in normalized
        ],
        "next_stage": (
            "maintain_quarterly_restore_history"
            if state == "trend_ready"
            else "accumulate_real_isolated_stg_restore_history"
        ),
        "production_restore_claimed": False,
        "production_touched": False,
        "generated_at": generated_at.isoformat(),
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["evidence_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-glob", default=DEFAULT_GLOB)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = Path(args.output)
    try:
        report = build_trend(args.evidence_glob, output)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        failure = {
            "schema_version": "1.0.0",
            "control_id": "BACEN-04",
            "evidence_class": "restore_trend_readiness",
            "state": "invalid_history",
            "result": "failed",
            "error": str(exc),
            "production_restore_claimed": False,
            "production_touched": False,
            "generated_at": utc_now().isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps({"state": report["state"], "result": report["result"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
