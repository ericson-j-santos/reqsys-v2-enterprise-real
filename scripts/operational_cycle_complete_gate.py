#!/usr/bin/env python3
"""Operational Cycle Complete Gate.

Gate determinístico para consolidar se o ciclo operacional da Trilha D está
completo, sem depender de snapshots temporais versionados.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = "artifacts/runtime-governance/operational-cycle-complete-gate.json"

REQUIRED_FLAGS = (
    "artifact_ingestion_enabled",
    "continuous_monitoring_enabled",
    "continuous_trilha_d_monitoring_history_enabled",
    "coverage_targeted_ready",
    "governance_deep_links_enabled",
    "artifact_ingestion_refresh_enabled",
    "merge_readiness_history_enabled",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def evaluate_operational_cycle(payload: dict[str, Any]) -> dict[str, Any]:
    summary = resolve_summary(payload)
    missing_flags = [flag for flag in REQUIRED_FLAGS if not bool(summary.get(flag))]
    current_score = float(payload.get("current_score") or 0.0)
    state = str(payload.get("state") or "unknown").lower()
    score_ready = current_score >= 98.0
    state_ready = state == "green"
    complete = not missing_flags and score_ready and state_ready

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "status": "green" if complete else "yellow",
        "color": "green" if complete else "yellow",
        "operational_cycle_complete": complete,
        "score_ready": score_ready,
        "state_ready": state_ready,
        "current_score": current_score,
        "state": state,
        "required_flags": list(REQUIRED_FLAGS),
        "missing_flags": missing_flags,
        "next_action": (
            "consolidar_ciclo_operacional"
            if complete
            else "resolver_flags_pendentes_antes_de_consolidar"
        ),
        "runtime_impact": "none",
    }


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avalia conclusão do ciclo operacional da Trilha D.")
    parser.add_argument(
        "--input",
        default="docs/ops-dashboard/data/trilha-d-history.json",
        help="Arquivo JSON de histórico da Trilha D.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Arquivo de saída do relatório.")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório JSON no stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_operational_cycle(load_json(args.input))
    write_report(report, args.output)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            " ".join(
                [
                    f"status={report['status']}",
                    f"operational_cycle_complete={report['operational_cycle_complete']}",
                    f"missing_flags={len(report['missing_flags'])}",
                    f"next_action={report['next_action']}",
                ]
            )
        )
    return 0 if report["operational_cycle_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
