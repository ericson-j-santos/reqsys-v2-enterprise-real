#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}


def build_runtime_ux_evidence(
    homologation: dict[str, Any],
    *,
    source_run_id: str,
    source_head_sha: str,
    source_workflow: str,
) -> list[dict[str, Any]]:
    if homologation.get("contract") != "fly-environment-homologation-gate":
        raise ValueError("contrato de homologação inválido")
    if homologation.get("ok") is not True:
        raise ValueError("homologação reprovada")

    environment = str(homologation.get("environment") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("ambiente inválido")
    if not source_run_id.strip():
        raise ValueError("source_run_id obrigatório")
    if len(source_head_sha.strip()) < 7:
        raise ValueError("source_head_sha inválido")

    probes = [item for item in homologation.get("probes") or [] if isinstance(item, dict)]
    critical = [item for item in probes if item.get("critical") is True]
    if not critical:
        raise ValueError("nenhum probe crítico disponível")

    successful = [item for item in critical if item.get("ok") is True]
    durations_ms = [
        float(item["duration_ms"])
        for item in critical
        if isinstance(item.get("duration_ms"), (int, float)) and item["duration_ms"] >= 0
    ]
    if not durations_ms:
        raise ValueError("duração dos probes críticos indisponível")

    recovery_rate = round((len(successful) / len(critical)) * 100, 2)
    average_recovery_seconds = round(sum(durations_ms) / len(durations_ms) / 1000, 3)
    observed_sha = str(homologation.get("observed_sha") or source_head_sha).strip()

    return [
        {
            "schema_version": "1.0.0",
            "contract": "reqsys-runtime-ux-recovery-evidence",
            "evidence_source": "runtime",
            "environment": environment,
            "source_workflow": source_workflow,
            "source_run_id": source_run_id,
            "source_head_sha": observed_sha,
            "correlation_id": homologation.get("correlation_id"),
            "recovery_rate": recovery_rate,
            "average_recovery_seconds": average_recovery_seconds,
            "ux_100_ready": recovery_rate == 100.0,
            "critical_journeys_total": len(critical),
            "critical_journeys_successful": len(successful),
            "observed_at": datetime.fromtimestamp(
                int(homologation.get("generated_at_epoch") or 0), timezone.utc
            ).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "advisory",
            "production_blocker": False,
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--homologation", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    homologation = json.loads(args.homologation.read_text(encoding="utf-8"))
    if not isinstance(homologation, dict):
        raise ValueError("homologation deve conter objeto JSON")

    result = build_runtime_ux_evidence(
        homologation,
        source_run_id=args.source_run_id,
        source_head_sha=args.source_head_sha,
        source_workflow=args.source_workflow,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"environment": result[0]["environment"], "recovery_rate": result[0]["recovery_rate"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
