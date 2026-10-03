#!/usr/bin/env python3
"""Executa benchmark reproduzível de análise de impacto de CHANGE."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.change_impact_analysis import (  # noqa: E402
    ChangeImpactValidationError,
    build_configured_llm_generator,
    evaluate_strategy,
    graph_candidates,
    hybrid_candidates,
    load_dataset,
    semantic_candidates,
)

DEFAULT_DATASET = ROOT / "data" / "change-impact" / "historical-ground-truth-v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "change-impact" / "benchmark-v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--llm-mode",
        choices=("disabled", "configured"),
        default="disabled",
        help="configured usa o AI Provider Router do ReqSys; disabled valida apenas recuperação.",
    )
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default="")
    parser.add_argument("--require-llm", action="store_true")
    parser.add_argument("--correlation-id", default="change-impact-benchmark-v1")
    return parser.parse_args()


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {
            "cases": 0,
            "mean_recall": 0.0,
            "mean_precision": 0.0,
            "mean_review_rate": 0.0,
        }
    return {
        "cases": len(rows),
        "mean_recall": round(mean(row["recall"] for row in rows), 4),
        "mean_precision": round(mean(row["precision"] for row in rows), 4),
        "mean_review_rate": round(mean(row["review_rate"] for row in rows), 4),
    }


def main() -> int:
    args = parse_args()
    if args.require_llm and args.llm_mode != "configured":
        raise SystemExit("--require-llm exige --llm-mode configured")

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    artifacts, changes = load_dataset(payload)

    llm_generate = None
    if args.llm_mode == "configured":
        llm_generate = build_configured_llm_generator(
            provider=args.provider,
            model=args.model,
        )

    rows: list[dict] = []
    llm_used_for_all = True
    for change in changes:
        results = (
            graph_candidates(change, artifacts),
            semantic_candidates(change, artifacts),
            hybrid_candidates(
                change,
                artifacts,
                llm_generate=llm_generate,
                correlation_id=f"{args.correlation_id}-{change.change_id}",
            ),
        )
        for result in results:
            metrics = asdict(evaluate_strategy(change, result, artifacts))
            metrics["change_id"] = change.change_id
            metrics["candidate_ids"] = [item.artifact_id for item in result.candidates]
            rows.append(metrics)
            if result.strategy == "hybrid_rag_llm" and result.llm_status != "used":
                llm_used_for_all = False

    by_strategy: dict[str, list[dict]] = {}
    for row in rows:
        by_strategy.setdefault(row["strategy"], []).append(row)

    dataset_display = (
        str(args.dataset.relative_to(ROOT))
        if args.dataset.is_relative_to(ROOT)
        else str(args.dataset)
    )
    result = {
        "schema_version": "1.0.0",
        "dataset": dataset_display,
        "correlation_id": args.correlation_id,
        "llm_mode": args.llm_mode,
        "llm_used_for_all_cases": llm_used_for_all,
        "cases": rows,
        "aggregate": {
            strategy: _aggregate(items)
            for strategy, items in sorted(by_strategy.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.require_llm and not llm_used_for_all:
        print("CHANGE_IMPACT_LLM_REQUIRED_BUT_NOT_USED", file=sys.stderr)
        return 3

    print(json.dumps(result["aggregate"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ChangeImpactValidationError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"CHANGE_IMPACT_BENCHMARK_FAILED:{type(exc).__name__}", file=sys.stderr)
        raise SystemExit(2) from exc
