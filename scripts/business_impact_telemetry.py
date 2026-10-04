#!/usr/bin/env python3
"""Consolida métricas observáveis de impacto negocial a partir de evidência CI/PR.

Não estima ROI. Métricas sem fonte objetiva permanecem explicitamente indisponíveis.
"""
from __future__ import annotations
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNAVAILABLE = {"status": "unavailable", "reason": "objective_source_not_available"}

def parse_dt(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

def median_minutes(values):
    return round(statistics.median(values), 2) if values else None

def analyze(pulls: list[dict[str, Any]], recoveries: list[dict[str, Any]], *, source_sha: str):
    pr_to_merge = []
    for pr in pulls:
        created, merged = parse_dt(pr.get("created_at")), parse_dt(pr.get("merged_at"))
        if created and merged and merged >= created:
            pr_to_merge.append((merged-created).total_seconds()/60)

    failure_to_recovery = []
    for item in recoveries:
        failed, recovered = parse_dt(item.get("failed_at")), parse_dt(item.get("recovered_at"))
        if failed and recovered and recovered >= failed:
            failure_to_recovery.append((recovered-failed).total_seconds()/60)

    return {
        "schema_version": "1.0",
        "source_sha": source_sha,
        "measurement_policy": "observed_only_no_roi_estimation",
        "metrics": {
            "pr_to_merge_minutes": {
                "status": "observed" if pr_to_merge else "unavailable",
                "sample_size": len(pr_to_merge),
                "median": median_minutes(pr_to_merge),
            },
            "failure_to_recovery_minutes": {
                "status": "observed" if failure_to_recovery else "unavailable",
                "sample_size": len(failure_to_recovery),
                "median": median_minutes(failure_to_recovery),
            },
            "human_intervention_rate": dict(UNAVAILABLE),
            "hours_saved": dict(UNAVAILABLE),
            "cost_per_execution": dict(UNAVAILABLE),
            "roi_percent": dict(UNAVAILABLE),
        },
    }

def main():
    source = Path("audit/business-impact/source.json")
    if not source.exists():
        raise SystemExit("missing audit/business-impact/source.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    report = analyze(payload.get("pulls", []), payload.get("recoveries", []), source_sha=str(payload.get("source_sha") or ""))
    out = Path("audit/business-impact/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
