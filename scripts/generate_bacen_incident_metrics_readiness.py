#!/usr/bin/env python3
"""Gera prontidão BACEN-03 para métricas reais de incidentes sem fabricar dados."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_METRICS = "governance/bacen/BACEN-03-INCIDENT-METRICS.json"
DEFAULT_OUTPUT = "artifacts/bacen/bacen-03-incident-metrics-readiness.json"


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


def validate_reference(value: Any) -> str:
    reference = str(value or "").strip()
    if not reference:
        raise ValueError("source_reference é obrigatório")
    parsed = urlparse(reference)
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.netloc != "github.com":
            raise ValueError("source_reference externo deve ser HTTPS do GitHub")
        return reference
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("source_reference relativo inseguro")
    return reference


def validate_metrics(document: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "control_id",
        "period_start",
        "period_end",
        "total_incidents",
        "sla_met_incidents",
        "mean_time_to_detect_minutes",
        "mean_time_to_recover_minutes",
        "open_corrective_actions",
        "overdue_corrective_actions",
        "source_reference",
        "human_reviewed",
    }
    missing = sorted(required - set(document))
    if missing:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(missing)}")
    if document["schema_version"] != "1.0.0":
        raise ValueError("schema_version deve ser 1.0.0")
    if document["control_id"] != "BACEN-03":
        raise ValueError("control_id deve ser BACEN-03")

    period_start = parse_datetime(document["period_start"], "period_start")
    period_end = parse_datetime(document["period_end"], "period_end")
    if period_end < period_start:
        raise ValueError("period_end não pode anteceder period_start")

    numeric_fields = (
        "total_incidents",
        "sla_met_incidents",
        "mean_time_to_detect_minutes",
        "mean_time_to_recover_minutes",
        "open_corrective_actions",
        "overdue_corrective_actions",
    )
    values: dict[str, int | float] = {}
    for field in numeric_fields:
        value = document[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field} deve ser número não negativo")
        values[field] = value

    if values["sla_met_incidents"] > values["total_incidents"]:
        raise ValueError("sla_met_incidents não pode exceder total_incidents")
    if values["overdue_corrective_actions"] > values["open_corrective_actions"]:
        raise ValueError("overdue_corrective_actions não pode exceder open_corrective_actions")
    if not isinstance(document["human_reviewed"], bool):
        raise ValueError("human_reviewed deve ser booleano")

    return {
        **document,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "source_reference": validate_reference(document["source_reference"]),
    }


def build_readiness(
    metrics_path: Path,
    output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if not metrics_path.is_file():
        report: dict[str, Any] = {
            "schema_version": "1.0.0",
            "control_id": "BACEN-03",
            "evidence_class": "real_incident_metrics_readiness",
            "metrics_present": False,
            "state": "pending_real_metrics",
            "result": "advisory",
            "next_stage": "ingest_real_incident_metrics_and_complete_human_review",
            "generated_at": generated_at.isoformat(),
            "production_touched": False,
        }
    else:
        raw = metrics_path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("o documento de métricas deve ser um objeto JSON")
        metrics = validate_metrics(document)
        total = int(metrics["total_incidents"])
        sla_met = int(metrics["sla_met_incidents"])
        sla_rate = round((sla_met / total) * 100.0, 2) if total else 100.0
        human_reviewed = bool(metrics["human_reviewed"])
        state = "metrics_ready" if human_reviewed else "metrics_ready_pending_human_review"
        report = {
            "schema_version": "1.0.0",
            "control_id": "BACEN-03",
            "evidence_class": "real_incident_metrics_readiness",
            "metrics_present": True,
            "state": state,
            "result": "passed" if human_reviewed else "advisory",
            "period_start": metrics["period_start"],
            "period_end": metrics["period_end"],
            "total_incidents": total,
            "sla_met_incidents": sla_met,
            "sla_rate_percent": sla_rate,
            "mean_time_to_detect_minutes": metrics["mean_time_to_detect_minutes"],
            "mean_time_to_recover_minutes": metrics["mean_time_to_recover_minutes"],
            "open_corrective_actions": metrics["open_corrective_actions"],
            "overdue_corrective_actions": metrics["overdue_corrective_actions"],
            "source_reference": metrics["source_reference"],
            "human_reviewed": human_reviewed,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "next_stage": (
                "maintain_quarterly_real_metrics_review"
                if human_reviewed
                else "complete_authenticated_human_review"
            ),
            "generated_at": generated_at.isoformat(),
            "production_touched": False,
        }

    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["evidence_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default=DEFAULT_METRICS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = Path(args.output)
    try:
        report = build_readiness(Path(args.metrics), output)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        failure = {
            "schema_version": "1.0.0",
            "control_id": "BACEN-03",
            "evidence_class": "real_incident_metrics_readiness",
            "state": "invalid_metrics",
            "result": "failed",
            "error": str(exc),
            "generated_at": utc_now().isoformat(),
            "production_touched": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps({"state": report["state"], "result": report["result"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
