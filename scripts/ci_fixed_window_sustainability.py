#!/usr/bin/env python3
from __future__ import annotations

import math
from typing import Any


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _eligible(item: dict[str, Any]) -> bool:
    window = item.get("collection_window") or {}
    return (
        window.get("mode") == "fixed_time"
        and window.get("sample_eligible") is True
        and window.get("collection_complete") is True
        and bool(window.get("policy_id"))
        and bool(window.get("window_id"))
    )


def _metric_signal(delta: float, *, lower_is_better: bool, tolerance: float) -> str:
    if abs(delta) <= tolerance:
        return "stable"
    improved = delta < 0 if lower_is_better else delta > 0
    return "improved" if improved else "regressed"


def transition(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    before = previous.get("current") or {}
    after = current.get("current") or {}
    specs = {
        "success_rate_percent": (False, 0.5),
        "failure_rate_percent": (True, 0.5),
        "p95_seconds": (True, 1.0),
        "cv_percent": (True, 0.5),
    }
    delta: dict[str, float] = {}
    signals: dict[str, str] = {}
    for key, (lower_is_better, tolerance) in specs.items():
        value = round(float(after.get(key, 0)) - float(before.get(key, 0)), 2)
        delta[key] = value
        signals[key] = _metric_signal(value, lower_is_better=lower_is_better, tolerance=tolerance)
    improved = list(signals.values()).count("improved")
    regressed = list(signals.values()).count("regressed")
    if improved >= 2 and improved > regressed:
        overall = "improved"
    elif regressed >= 2 and regressed > improved:
        overall = "regressed"
    elif improved == 0 and regressed == 0:
        overall = "stable"
    else:
        overall = "mixed"
    return {"overall_signal": overall, "delta": delta, "signals": signals}


def _window_key(item: dict[str, Any]) -> str:
    window = item.get("collection_window") or {}
    return str(window.get("window_id") or item.get("run_id") or item.get("generated_at") or "")


def _series_item(item: dict[str, Any], trend_signal: str | None = None) -> dict[str, Any]:
    window = item.get("collection_window") or {}
    current = item.get("current") or {}
    return {
        "generated_at": item.get("generated_at"),
        "run_id": item.get("run_id"),
        "window_id": window.get("window_id"),
        "policy_id": window.get("policy_id"),
        "start_at": window.get("start_at"),
        "end_at": window.get("end_at"),
        "sample_eligible": _eligible(item),
        "eligibility_reason_codes": list(window.get("eligibility_reason_codes") or []),
        "completion_coverage_percent": window.get("completion_coverage_percent"),
        "trend_signal": trend_signal,
        "baseline_signal": (item.get("baseline_comparison") or {}).get("overall_signal"),
        "success_rate_percent": current.get("success_rate_percent"),
        "failure_rate_percent": current.get("failure_rate_percent"),
        "p95_seconds": current.get("p95_seconds"),
        "cv_percent": current.get("cv_percent"),
    }


def summarize_history(records: list[dict[str, Any]], lookback: int = 5) -> dict[str, Any]:
    ordered = sorted(records, key=lambda item: str(item.get("generated_at") or ""))
    # Defesa extra contra artefatos duplicados da mesma hora.
    deduped: dict[str, dict[str, Any]] = {}
    for item in ordered:
        deduped[_window_key(item)] = item
    ordered = sorted(deduped.values(), key=lambda item: str(item.get("generated_at") or ""))

    eligible_all = [item for item in ordered if _eligible(item)]
    active_policy = (eligible_all[-1].get("collection_window") or {}).get("policy_id") if eligible_all else None
    homogeneous = [
        item for item in eligible_all
        if (item.get("collection_window") or {}).get("policy_id") == active_policy
    ]
    recent = homogeneous[-lookback:]
    transitions = [transition(recent[i - 1], recent[i]) for i in range(1, len(recent))]
    signals = [item["overall_signal"] for item in transitions]
    improved = signals.count("improved")
    regressed = signals.count("regressed")
    stable = signals.count("stable")
    mixed = signals.count("mixed")

    if len(recent) < 3:
        sustainability = "insufficient_data"
    elif improved >= math.ceil(len(transitions) * 0.6) and regressed == 0:
        sustainability = "sustained_improvement"
    elif regressed >= math.ceil(len(transitions) * 0.4):
        sustainability = "regression_watch"
    else:
        sustainability = "mixed"

    series = []
    for idx, item in enumerate(recent):
        signal = None if idx == 0 else transitions[idx - 1]["overall_signal"]
        series.append(_series_item(item, signal))
    current = [item.get("current") or {} for item in recent]
    return {
        "available": bool(records),
        "mode": "report-only",
        "creates_gate": False,
        "sustainability_basis": "homogeneous_fixed_time_windows",
        "active_policy_id": active_policy,
        "records": len(ordered),
        "eligible_records": len(homogeneous),
        "excluded_ineligible_records": len(ordered) - len(homogeneous),
        # aliases mantidos para consumidores antigos do Command Center
        "comparable_records": len(homogeneous),
        "excluded_non_comparable_records": len(ordered) - len(homogeneous),
        "lookback": len(recent),
        "requested_lookback": lookback,
        "transition_count": len(transitions),
        "sustainability": sustainability,
        "signals": {
            "improved": improved,
            "stable": stable,
            "regressed": regressed,
            "mixed": mixed,
        },
        "recent_averages": {
            "success_rate_percent": _avg([float(item.get("success_rate_percent", 0)) for item in current]),
            "failure_rate_percent": _avg([float(item.get("failure_rate_percent", 0)) for item in current]),
            "p95_seconds": _avg([float(item.get("p95_seconds", 0)) for item in current]),
            "cv_percent": _avg([float(item.get("cv_percent", 0)) for item in current]),
        },
        "series": series,
        "recent_context": [_series_item(item) for item in ordered[-lookback:]],
        "transitions": transitions,
    }
