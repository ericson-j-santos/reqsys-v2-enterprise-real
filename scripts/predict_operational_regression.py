#!/usr/bin/env python3
"""Predictive Operational Regression Gate.

Usa tendência do histórico da Trilha D para sinalizar regressão operacional
antes do merge. Primeira versão determinística, sem IA.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.build_trilha_d_history import DIMENSIONS, trend_for

CRITICAL_DIMENSIONS = {"tests", "coverage"}
DIMENSION_PATH_HINTS: dict[str, tuple[str, ...]] = {
    "tests": ("backend/tests/", "tests/test_"),
    "coverage": ("backend/tests/", "backend/app/"),
    "mutation": ("backend/tests/", "backend/app/"),
    "contract": ("docs/contracts/", "docs/schema-registry.json"),
    "schema": ("docs/contracts/", "docs/schema-registry.json"),
    "ci-watch": (".github/workflows/",),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON inválido em {path}")
    return payload


def load_paths(raw_paths: list[str], paths_file: str | None = None) -> list[str]:
    paths = [item.strip() for item in raw_paths if item.strip()]
    if paths_file:
        file_path = Path(paths_file)
        if file_path.exists():
            paths.extend(item.strip() for item in file_path.read_text(encoding="utf-8").splitlines() if item.strip())
    return sorted(dict.fromkeys(paths))


def paths_touch_dimension(paths: list[str], dimension: str) -> bool:
    hints = DIMENSION_PATH_HINTS.get(dimension, ())
    return any(path.startswith(hint) or hint in path for path in paths for hint in hints)


def affected_dimensions(paths: list[str]) -> list[str]:
    touched = [dimension for dimension in DIMENSIONS if paths_touch_dimension(paths, dimension)]
    return sorted(touched)


def recent_failed_samples(history: list[dict[str, Any]], window: int = 2) -> int:
    recent = history[-window:] if window > 0 else history
    return sum(1 for item in recent if item.get("state") == "failed")


def regressing_dimensions(dimension_summary: dict[str, Any]) -> list[str]:
    return sorted(
        dimension
        for dimension in DIMENSIONS
        if (dimension_summary.get(dimension) or {}).get("trend") == "regressing"
    )


def predict_operational_regression(
    history_index: dict[str, Any],
    *,
    current_report: dict[str, Any] | None = None,
    changed_paths: list[str] | None = None,
    min_samples: int = 2,
    mode: str = "report_only",
) -> dict[str, Any]:
    history = list(history_index.get("history") or [])
    dimension_summary = history_index.get("dimension_summary") or {}
    average_values = [
        float(item["average_score"])
        for item in history
        if isinstance(item.get("average_score"), int | float)
    ]
    overall_trend = str(history_index.get("trend") or trend_for(average_values))
    regressing = regressing_dimensions(dimension_summary)
    critical_regressing = [dimension for dimension in regressing if dimension in CRITICAL_DIMENSIONS]
    recent_failures = recent_failed_samples(history)
    insufficient_history = len(history) < min_samples

    projected_drop = False
    projected_delta = 0.0
    if current_report is not None:
        current_score = float(history_index.get("current_score") or 0.0)
        projected_score = float(current_report.get("average_score") or current_score)
        projected_delta = round(projected_score - current_score, 2)
        projected_drop = projected_delta <= -2

    touched = affected_dimensions(changed_paths or [])
    touched_regressing = sorted(set(touched).intersection(regressing))

    blocking_reasons: list[str] = []
    risk = "low"
    regression_predicted = False

    if insufficient_history:
        blocking_reasons.append("insufficient_history")
    if overall_trend == "regressing":
        blocking_reasons.append("overall_trend_regressing")
        regression_predicted = True
        risk = "medium"
    if regressing:
        blocking_reasons.append("dimension_trend_regressing")
        regression_predicted = True
        risk = "high" if critical_regressing else "medium"
    if recent_failures > 0:
        blocking_reasons.append("recent_failed_samples")
        regression_predicted = True
        risk = "high"
    if projected_drop:
        blocking_reasons.append("projected_score_drop")
        regression_predicted = True
        if risk not in {"high", "blocked"}:
            risk = "high"

    if touched_regressing:
        blocking_reasons.append("changed_paths_touch_regressing_dimensions")
        regression_predicted = True
        if mode == "blocking":
            risk = "blocked"
        elif risk == "low":
            risk = "high"

    if insufficient_history and risk == "low" and not regression_predicted:
        if "insufficient_history" not in blocking_reasons:
            blocking_reasons.append("insufficient_history")

    parallel_safe = risk in {"low", "medium"} and risk != "blocked"
    if risk == "blocked":
        parallel_safe = False

    if risk == "blocked":
        recommendation = "serializar_merge"
    elif risk == "high":
        recommendation = "merge_com_atencao"
    elif risk == "medium":
        recommendation = "validar_regressao_antes_de_merge"
    else:
        recommendation = "merge_paralelo_seguro"

    dimension_risks = {
        dimension: {
            "trend": (dimension_summary.get(dimension) or {}).get("trend", "unknown"),
            "current_score": (dimension_summary.get(dimension) or {}).get("current_score"),
            "touched_by_pr": dimension in touched,
            "regressing": dimension in regressing,
        }
        for dimension in DIMENSIONS
    }

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "mode": mode,
        "risk": risk,
        "regression_predicted": regression_predicted,
        "lane": "predictive-governance",
        "parallel_safe": parallel_safe,
        "blocking_reasons": blocking_reasons,
        "recommendation": recommendation,
        "signals": {
            "insufficient_history": insufficient_history,
            "overall_trend": overall_trend,
            "current_score": history_index.get("current_score"),
            "baseline_score": history_index.get("baseline_score"),
            "delta_from_baseline": history_index.get("delta_from_baseline"),
            "recent_failed_samples": recent_failures,
            "regressing_dimensions": regressing,
            "critical_regressing_dimensions": critical_regressing,
            "projected_score_delta": projected_delta,
            "projected_drop": projected_drop,
            "changed_paths_count": len(changed_paths or []),
            "affected_dimensions": touched,
            "touched_regressing_dimensions": touched_regressing,
        },
        "dimension_risks": dimension_risks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prediz regressão operacional a partir do histórico da Trilha D.")
    parser.add_argument("--history-json", default="docs/ops-dashboard/data/trilha-d-history.json")
    parser.add_argument("--report-json", default="", help="Relatório consolidado opcional da execução atual")
    parser.add_argument("paths", nargs="*", help="Paths alterados")
    parser.add_argument("--paths-file", default="", help="Arquivo com um path por linha")
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument(
        "--mode",
        default="report_only",
        choices=("report_only", "advisory", "blocking"),
        help="report_only nunca falha; blocking falha em risco alto/bloqueado",
    )
    parser.add_argument("--output", default="artifacts/runtime-governance/predict-operational-regression-gate.json")
    parser.add_argument("--json", action="store_true")
    return parser


def should_fail(payload: dict[str, Any]) -> bool:
    mode = str(payload.get("mode") or "report_only")
    risk = str(payload.get("risk") or "low")
    if mode == "blocking" and risk in {"high", "blocked"}:
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    history_index = load_json(args.history_json)
    current_report = load_json(args.report_json) if args.report_json else None
    changed_paths = load_paths(args.paths, args.paths_file or None)
    payload = predict_operational_regression(
        history_index,
        current_report=current_report,
        changed_paths=changed_paths,
        min_samples=args.min_samples,
        mode=args.mode,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            f"risk={payload['risk']} regression_predicted={payload['regression_predicted']} "
            f"recommendation={payload['recommendation']}"
        )

    return 1 if should_fail(payload) else 0


if __name__ == "__main__":
    raise SystemExit(main())
