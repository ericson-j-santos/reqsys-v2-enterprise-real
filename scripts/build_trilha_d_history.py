#!/usr/bin/env python3
"""Build Trilha D History Index.

Gera um JSON estático consumível pelo dashboard operacional com histórico,
tendência e regressão das dimensões da Trilha D.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/trilha-d-history.json"
DIMENSIONS = ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def trend_for(values: list[float]) -> str:
    if len(values) < 2:
        return "stable"
    delta = round(values[-1] - values[0], 2)
    if delta >= 2:
        return "improving"
    if delta <= -2:
        return "regressing"
    return "stable"


def build_sample_history() -> list[dict[str, Any]]:
    return [
        {
            "timestamp": "2026-06-28T00:50:55Z",
            "source": "github_actions_artifact",
            "run_id": "28306826456",
            "state": "failed",
            "average_score": 88.33,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "failed", "score": 29.0},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["baseline_before_coverage_parser_fix"],
        },
        {
            "timestamp": "2026-06-28T01:39:18Z",
            "source": "merged_pr",
            "run_id": "pr-462",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_fix_merged"],
        },
        {
            "timestamp": "2026-06-28T01:43:44Z",
            "source": "merged_pr",
            "run_id": "pr-463",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_regression_tests_merged"],
        },
    ]


def dimension_values(history: list[dict[str, Any]], dimension: str) -> list[float]:
    values: list[float] = []
    for item in history:
        dim = item.get("dimensions", {}).get(dimension, {})
        score = dim.get("score")
        if isinstance(score, int | float):
            values.append(float(score))
    return values


def build_dimension_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for dimension in DIMENSIONS:
        values = dimension_values(history, dimension)
        last_status = history[-1].get("dimensions", {}).get(dimension, {}).get("status", "unknown") if history else "unknown"
        summary[dimension] = {
            "current_status": last_status,
            "current_score": round(values[-1], 2) if values else None,
            "previous_score": round(values[-2], 2) if len(values) >= 2 else None,
            "delta_from_baseline": round(values[-1] - values[0], 2) if len(values) >= 2 else 0.0,
            "trend": trend_for(values),
            "samples": len(values),
        }
    return summary


def build_payload(history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    samples = history or build_sample_history()
    average_values = [float(item["average_score"]) for item in samples if isinstance(item.get("average_score"), int | float)]
    current_score = round(average_values[-1], 2) if average_values else 0.0
    baseline_score = round(average_values[0], 2) if average_values else 0.0
    delta = round(current_score - baseline_score, 2)
    state = "green" if current_score >= 90 and all(item["state"] == "green" for item in samples[-2:]) else "yellow"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "current_score": current_score,
        "baseline_score": baseline_score,
        "delta_from_baseline": delta,
        "trend": trend_for(average_values),
        "summary": {
            "samples": len(samples),
            "green_samples": sum(1 for item in samples if item.get("state") == "green"),
            "failed_samples": sum(1 for item in samples if item.get("state") == "failed"),
            "next_increment": "surface_trilha_d_history_in_ops_dashboard",
        },
        "links": {
            "actions": f"https://github.com/{REPO}/actions/workflows/trilha-d-qualidade-governanca.yml",
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_trilha_d_history.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
        },
        "dimension_summary": build_dimension_summary(samples),
        "history": samples,
        "runtime_dashboard_contract": {
            "card_fields": ["state", "current_score", "trend", "delta_from_baseline"],
            "series_fields": ["timestamp", "average_score", "state"],
            "dimension_fields": ["current_status", "current_score", "trend", "delta_from_baseline"],
            "refresh_strategy": "static_json_until_artifact_ingestion_is_enabled",
        },
    }


def write_payload(output_path: str) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera trilha-d-history.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"trilha_d_history_state={payload['state']} score={payload['current_score']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
