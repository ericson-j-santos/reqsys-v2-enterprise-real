#!/usr/bin/env python3
"""Evaluate temporal regression for Runtime Executive post-deploy history.

This gate is deterministic and offline: it reads the bounded history JSON and
emits a regression report. In strict mode it exits non-zero when production
should be blocked by temporal regression.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


DEFAULT_HISTORY = Path("docs/ops-dashboard/data/runtime-executive-post-deploy-history.json")
DEFAULT_OUTPUT = Path("artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json")
DEFAULT_BRIEF = Path("docs/ops-dashboard/data/executive-brief.json")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def numeric(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def recent_window(history: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    return history[-max(1, window):]


def consecutive_score_down(history: list[dict[str, Any]], count: int) -> bool:
    if len(history) < count + 1:
        return False
    scores = [numeric(item.get("executive_score"), 0) for item in history[-(count + 1):]]
    return all(scores[index] < scores[index - 1] for index in range(1, len(scores)))


def evaluate(history_payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    history = history_payload.get("history") or []
    summary = history_payload.get("summary") or {}
    recent = recent_window(history, args.window)
    recent_failures = sum(int(item.get("failure_count") or 0) for item in recent)
    recent_failure_rate = round(recent_failures / len(recent), 4) if recent else 0.0
    availability = numeric(summary.get("availability_percent"), 0)
    avg_latency = summary.get("avg_latency_ms")
    avg_latency_value = numeric(avg_latency, 0) if avg_latency is not None else None
    score_down = consecutive_score_down(history, args.score_drop_runs)

    violations: list[dict[str, Any]] = []
    if history and availability < args.min_availability:
        violations.append({
            "code": "availability_below_threshold",
            "severity": "critical",
            "observed": availability,
            "threshold": args.min_availability,
            "detail": "disponibilidade historica abaixo do limite governado",
        })
    if avg_latency_value is not None and avg_latency_value > args.max_avg_latency_ms:
        violations.append({
            "code": "latency_above_threshold",
            "severity": "critical",
            "observed": avg_latency_value,
            "threshold": args.max_avg_latency_ms,
            "detail": "latencia media historica acima do limite governado",
        })
    if recent and recent_failure_rate > args.max_recent_failure_rate:
        violations.append({
            "code": "recent_failure_rate_above_threshold",
            "severity": "critical",
            "observed": recent_failure_rate,
            "threshold": args.max_recent_failure_rate,
            "detail": "taxa recente de falha acima do limite governado",
        })
    if score_down:
        violations.append({
            "code": "consecutive_score_drop",
            "severity": "warning",
            "observed": args.score_drop_runs,
            "threshold": args.score_drop_runs,
            "detail": "score executivo caiu por execucoes consecutivas",
        })

    production_blocked = any(item["severity"] == "critical" for item in violations) or (
        args.block_on_score_drop and score_down
    )
    status = "blocked" if production_blocked else "warning" if violations else "passed"
    risk = "high" if production_blocked else "medium" if violations else "low"

    return {
        "schema_version": "1.0.0",
        "contract": "runtime-executive-regression-alert",
        "evaluated_at_epoch": int(time.time()),
        "status": status,
        "production_blocked": production_blocked,
        "risk": risk,
        "window": args.window,
        "thresholds": {
            "min_availability": args.min_availability,
            "max_avg_latency_ms": args.max_avg_latency_ms,
            "max_recent_failure_rate": args.max_recent_failure_rate,
            "score_drop_runs": args.score_drop_runs,
            "block_on_score_drop": args.block_on_score_drop,
        },
        "observed": {
            "samples": len(history),
            "recent_samples": len(recent),
            "availability_percent": availability,
            "avg_latency_ms": avg_latency_value,
            "recent_failure_count": recent_failures,
            "recent_failure_rate": recent_failure_rate,
            "score_trend": summary.get("score_trend"),
            "latency_trend": summary.get("latency_trend"),
            "failure_trend": summary.get("failure_trend"),
            "stability": summary.get("stability"),
        },
        "violations": violations,
        "guardrails": [
            "offline_history_gate",
            "strict_mode_blocks_production",
            "thresholds_parameterized",
            "no_secret_required",
        ],
    }


def enrich_brief(brief_path: Path, report: dict[str, Any], report_path: str) -> None:
    brief = load_json(brief_path)
    if not brief:
        return
    estado = brief.setdefault("estado_unico", {})
    estado["runtime_executive_regression_alert"] = {
        "status": report.get("status"),
        "production_blocked": report.get("production_blocked"),
        "risk": report.get("risk"),
        "violations": report.get("violations") or [],
    }
    if report.get("production_blocked"):
        estado["pronto_para_producao"] = False
    indicadores = brief.setdefault("indicadores_executivos", {})
    indicadores["runtime_executive_regression_risk"] = report.get("risk")
    indicadores["runtime_executive_regression_blocked"] = report.get("production_blocked")
    links = brief.setdefault("links", {})
    links["runtime_executive_regression_alert"] = report_path
    write_json(brief_path, brief)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Runtime Executive temporal regression")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--executive-brief", type=Path, default=DEFAULT_BRIEF)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--min-availability", type=float, default=95.0)
    parser.add_argument("--max-avg-latency-ms", type=float, default=2500.0)
    parser.add_argument("--max-recent-failure-rate", type=float, default=0.2)
    parser.add_argument("--score-drop-runs", type=int, default=3)
    parser.add_argument("--block-on-score-drop", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history = load_json(args.history)
    if not history:
        report = {
            "schema_version": "1.0.0",
            "contract": "runtime-executive-regression-alert",
            "evaluated_at_epoch": int(time.time()),
            "status": "warning",
            "production_blocked": False,
            "risk": "medium",
            "violations": [{
                "code": "history_missing",
                "severity": "warning",
                "detail": "historico temporal ainda indisponivel",
            }],
            "guardrails": ["offline_history_gate", "safe_when_history_missing"],
        }
    else:
        report = evaluate(history, args)
    write_json(args.output, report)
    enrich_brief(args.executive_brief, report, str(args.output))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.strict and report.get("production_blocked"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
