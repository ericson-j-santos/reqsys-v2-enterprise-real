#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_ANALYTICS_PATH = Path("audit/ci-lead-time-analytics.json")
DEFAULT_MARKDOWN_PATH = Path("audit/ci-lead-time-analytics.md")
DEFAULT_BASELINE_PATH = Path("audit/baselines/ci-process-improvement-baseline-2026-09-02.json")
MIN_RATIO = 0.80
MAX_RATIO = 1.25


def _ratio(current: float | int | None, baseline: float | int | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return round(float(current) / float(baseline), 3)


def _sample_from_analytics(analytics: dict[str, Any]) -> dict[str, Any]:
    throughput = analytics.get("throughput") or {}
    completed = int(analytics.get("completed_runs") or 0)
    known = sum(
        int(analytics.get(key) or 0)
        for key in ("success_count", "failure_count", "cancelled_count", "skipped_count")
    )
    return {
        "window_runs": int(analytics.get("window_runs") or 0),
        "completed_runs": completed,
        "window_span_hours": throughput.get("window_span_hours"),
        "success_count": int(analytics.get("success_count") or 0),
        "failure_count": int(analytics.get("failure_count") or 0),
        "cancelled_count": int(analytics.get("cancelled_count") or 0),
        "skipped_count": int(analytics.get("skipped_count") or 0),
        "other_completed_count": max(0, completed - known),
    }


def _sample_from_baseline(baseline: dict[str, Any]) -> dict[str, Any] | None:
    sample = baseline.get("sample") or {}
    quality = baseline.get("quality") or {}
    required = (sample.get("window_runs"), sample.get("completed_runs"), sample.get("window_span_hours"))
    if any(value is None for value in required):
        return None
    completed = int(sample["completed_runs"])
    known = sum(int(quality.get(key) or 0) for key in ("success_count", "failure_count", "cancelled_count", "skipped_count"))
    return {
        "window_runs": int(sample["window_runs"]),
        "completed_runs": completed,
        "window_span_hours": float(sample["window_span_hours"]),
        "success_count": int(quality.get("success_count") or 0),
        "failure_count": int(quality.get("failure_count") or 0),
        "cancelled_count": int(quality.get("cancelled_count") or 0),
        "skipped_count": int(quality.get("skipped_count") or 0),
        "other_completed_count": max(0, completed - known),
    }


def build_window_comparability(analytics: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    current = _sample_from_analytics(analytics)
    common = {
        "mode": "descriptive-only",
        "creates_gate": False,
        "thresholds": {
            "completed_runs_ratio_min": MIN_RATIO,
            "completed_runs_ratio_max": MAX_RATIO,
            "window_span_ratio_min": MIN_RATIO,
            "window_span_ratio_max": MAX_RATIO,
        },
        "current_sample": current,
        "interpretation": "comparabilidade estrutural da amostra; não representa significância estatística nem prova causal",
    }
    if baseline is None:
        return {**common, "available": False, "comparable_to_baseline": False, "reason_codes": ["baseline_unavailable"]}

    baseline_sample = _sample_from_baseline(baseline)
    if baseline_sample is None:
        return {
            **common,
            "available": False,
            "comparable_to_baseline": False,
            "baseline_sample": None,
            "reason_codes": ["baseline_sample_metadata_incomplete"],
        }

    completed_ratio = _ratio(current["completed_runs"], baseline_sample["completed_runs"])
    span_ratio = _ratio(current["window_span_hours"], baseline_sample["window_span_hours"])
    reason_codes: list[str] = []
    if current["window_runs"] != baseline_sample["window_runs"]:
        reason_codes.append("window_runs_mismatch")
    if completed_ratio is None or not MIN_RATIO <= completed_ratio <= MAX_RATIO:
        reason_codes.append("completed_runs_ratio_out_of_range")
    if span_ratio is None or not MIN_RATIO <= span_ratio <= MAX_RATIO:
        reason_codes.append("window_span_ratio_out_of_range")

    return {
        **common,
        "available": True,
        "comparable_to_baseline": not reason_codes,
        "baseline_sample": baseline_sample,
        "ratios": {
            "completed_runs": completed_ratio,
            "window_span": span_ratio,
        },
        "reason_codes": reason_codes,
    }


def render_markdown_section(comparability: dict[str, Any]) -> str:
    lines = ["", "## Statistical window comparability"]
    lines.append(f"- Available: {'yes' if comparability.get('available') else 'no'}")
    lines.append(f"- Comparable to frozen baseline: {'yes' if comparability.get('comparable_to_baseline') else 'no'}")
    reasons = comparability.get("reason_codes") or []
    lines.append(f"- Reasons: {', '.join(reasons) if reasons else 'none'}")
    ratios = comparability.get("ratios") or {}
    if ratios:
        lines.append(f"- Completed-runs ratio: {ratios.get('completed_runs')}")
        lines.append(f"- Window-span ratio: {ratios.get('window_span')}")
    lines.append("- Mode: descriptive-only")
    lines.append("- Gate created: no")
    lines.append("- Interpretation: structural sample comparability only; not statistical significance or causation")
    return "\n".join(lines) + "\n"


def apply_window_comparability(analytics_path: Path, markdown_path: Path, baseline_path: Path) -> dict[str, Any]:
    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    baseline = None
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        baseline = None

    comparability = build_window_comparability(analytics, baseline)
    analytics["window_comparability"] = comparability
    analytics_path.write_text(json.dumps(analytics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    existing = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else "# CI Lead Time Analytics\n"
    marker = "\n## Statistical window comparability"
    if marker in existing:
        existing = existing.split(marker, 1)[0].rstrip() + "\n"
    markdown_path.write_text(existing.rstrip() + "\n" + render_markdown_section(comparability), encoding="utf-8")
    return analytics


def main() -> int:
    analytics_path = Path(os.environ.get("CI_ANALYTICS_PATH") or DEFAULT_ANALYTICS_PATH)
    markdown_path = Path(os.environ.get("CI_ANALYTICS_MARKDOWN_PATH") or DEFAULT_MARKDOWN_PATH)
    baseline_path = Path(os.environ.get("PROCESS_BASELINE_PATH") or DEFAULT_BASELINE_PATH)
    analytics = apply_window_comparability(analytics_path, markdown_path, baseline_path)
    print(json.dumps(analytics["window_comparability"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
