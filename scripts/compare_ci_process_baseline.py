#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_ANALYTICS_PATH = Path("audit/ci-lead-time-analytics.json")
DEFAULT_MARKDOWN_PATH = Path("audit/ci-lead-time-analytics.md")
DEFAULT_BASELINE_PATH = Path("audit/baselines/ci-process-improvement-baseline-2026-09-02.json")


def _signal(delta: float, *, lower_is_better: bool, tolerance: float) -> str:
    if abs(delta) <= tolerance:
        return "stable"
    improved = delta < 0 if lower_is_better else delta > 0
    return "improved" if improved else "regressed"


def _delta(current: float, baseline: float) -> float:
    return round(float(current) - float(baseline), 2)


def load_frozen_baseline(path: Path) -> dict[str, Any]:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("frozen") is not True:
        raise ValueError(f"baseline não está congelado: {path}")
    if baseline.get("governance", {}).get("mode") != "report-only":
        raise ValueError(f"baseline fora do modo report-only: {path}")
    return baseline


def build_baseline_comparison(
    summary: dict[str, Any],
    baseline: dict[str, Any] | None,
    *,
    baseline_path: str,
    unavailable_reason: str | None = None,
) -> dict[str, Any]:
    if baseline is None:
        return {
            "available": False,
            "mode": "report-only",
            "baseline_path": baseline_path,
            "reason": unavailable_reason or "baseline congelado não disponível",
            "creates_gate": False,
        }

    source = baseline.get("source", {})
    if source.get("repository") != summary.get("repository"):
        return {
            "available": False,
            "mode": "report-only",
            "baseline_path": baseline_path,
            "reason": "baseline pertence a outro repositório",
            "creates_gate": False,
        }

    quality = baseline["quality"]
    timing = baseline["time"]
    quality_delta = {
        "success_rate_pp": _delta(summary["success_rate_percent"], quality["success_rate_percent"]),
        "failure_rate_pp": _delta(summary["failure_rate_percent"], quality["failure_rate_percent"]),
        "first_pass_success_rate_pp": _delta(
            summary["first_pass_success_rate_percent"], quality["first_pass_success_rate_percent"]
        ),
        "rerun_rate_pp": _delta(summary["rerun_rate_percent"], quality["rerun_rate_percent"]),
    }
    speed_delta = {
        "avg_seconds": _delta(summary["avg_seconds"], timing["avg_seconds"]),
        "p50_seconds": _delta(summary["p50_seconds"], timing["p50_seconds"]),
        "p95_seconds": _delta(summary["p95_seconds"], timing["p95_seconds"]),
        "p95_queue_seconds": _delta(summary["p95_queue_seconds"], timing["p95_queue_seconds"]),
    }
    variability_delta = {
        "stddev_seconds": _delta(summary["stddev_seconds"], timing["stddev_seconds"]),
        "cv_percent": _delta(summary["cv_percent"], timing["cv_percent"]),
    }
    signals = {
        "quality": {
            "success_rate": _signal(quality_delta["success_rate_pp"], lower_is_better=False, tolerance=0.5),
            "failure_rate": _signal(quality_delta["failure_rate_pp"], lower_is_better=True, tolerance=0.5),
            "first_pass_success": _signal(
                quality_delta["first_pass_success_rate_pp"], lower_is_better=False, tolerance=0.5
            ),
            "rerun_rate": _signal(quality_delta["rerun_rate_pp"], lower_is_better=True, tolerance=0.5),
        },
        "speed": {
            "average": _signal(speed_delta["avg_seconds"], lower_is_better=True, tolerance=1.0),
            "p50": _signal(speed_delta["p50_seconds"], lower_is_better=True, tolerance=1.0),
            "p95": _signal(speed_delta["p95_seconds"], lower_is_better=True, tolerance=1.0),
            "queue_p95": _signal(speed_delta["p95_queue_seconds"], lower_is_better=True, tolerance=1.0),
        },
        "variability": {
            "stddev": _signal(variability_delta["stddev_seconds"], lower_is_better=True, tolerance=1.0),
            "cv": _signal(variability_delta["cv_percent"], lower_is_better=True, tolerance=0.5),
        },
    }
    flat_signals = [value for group in signals.values() for value in group.values()]
    if "regressed" in flat_signals and "improved" in flat_signals:
        overall = "mixed"
    elif "regressed" in flat_signals:
        overall = "regressed"
    elif "improved" in flat_signals:
        overall = "improved"
    else:
        overall = "stable"

    return {
        "available": True,
        "mode": "report-only",
        "baseline_path": baseline_path,
        "baseline": {
            "frozen_at": baseline.get("frozen_at"),
            "workflow_run_id": source.get("workflow_run_id"),
            "workflow_run_number": source.get("workflow_run_number"),
            "head_sha": source.get("head_sha"),
            "analytics_schema_version": source.get("analytics_schema_version"),
        },
        "delta": {
            "quality": quality_delta,
            "speed": speed_delta,
            "variability": variability_delta,
        },
        "signals": signals,
        "overall_signal": overall,
        "causality": "descriptive evidence only; deltas do not prove causation",
        "creates_gate": False,
    }


def render_markdown_section(comparison: dict[str, Any]) -> str:
    lines = ["", "## Frozen baseline comparison"]
    if not comparison.get("available"):
        lines.append(f"- Unavailable: {comparison.get('reason')}")
        lines.append("- Mode: report-only")
        lines.append("- Gate created: no")
        return "\n".join(lines) + "\n"

    quality = comparison["delta"]["quality"]
    speed = comparison["delta"]["speed"]
    variability = comparison["delta"]["variability"]
    signals = comparison["signals"]
    lines.extend(
        [
            f"- Mode: {comparison['mode']}",
            f"- Overall signal: {comparison['overall_signal']}",
            f"- Baseline run: {comparison['baseline']['workflow_run_id']}",
            f"- Success-rate delta: {quality['success_rate_pp']} pp ({signals['quality']['success_rate']})",
            f"- Failure-rate delta: {quality['failure_rate_pp']} pp ({signals['quality']['failure_rate']})",
            f"- First-pass delta: {quality['first_pass_success_rate_pp']} pp ({signals['quality']['first_pass_success']})",
            f"- Rerun-rate delta: {quality['rerun_rate_pp']} pp ({signals['quality']['rerun_rate']})",
            f"- P50 delta: {speed['p50_seconds']}s ({signals['speed']['p50']})",
            f"- P95 delta: {speed['p95_seconds']}s ({signals['speed']['p95']})",
            f"- CV delta: {variability['cv_percent']} pp ({signals['variability']['cv']})",
            "- Gate created: no",
        ]
    )
    return "\n".join(lines) + "\n"


def apply_baseline_comparison(
    analytics_path: Path,
    markdown_path: Path,
    baseline_path: Path,
) -> dict[str, Any]:
    summary = json.loads(analytics_path.read_text(encoding="utf-8"))
    baseline = None
    unavailable_reason = None
    try:
        baseline = load_frozen_baseline(baseline_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        unavailable_reason = str(exc)

    comparison = build_baseline_comparison(
        summary,
        baseline,
        baseline_path=str(baseline_path),
        unavailable_reason=unavailable_reason,
    )
    summary["schema_version"] = "1.0.3"
    summary["baseline_comparison"] = comparison
    analytics_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    existing_markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else "# CI Lead Time Analytics\n"
    marker = "\n## Frozen baseline comparison"
    if marker in existing_markdown:
        existing_markdown = existing_markdown.split(marker, 1)[0].rstrip() + "\n"
    markdown_path.write_text(existing_markdown.rstrip() + "\n" + render_markdown_section(comparison), encoding="utf-8")
    return summary


def main() -> int:
    analytics_path = Path(os.environ.get("CI_ANALYTICS_PATH") or DEFAULT_ANALYTICS_PATH)
    markdown_path = Path(os.environ.get("CI_ANALYTICS_MARKDOWN_PATH") or DEFAULT_MARKDOWN_PATH)
    baseline_path = Path(os.environ.get("PROCESS_BASELINE_PATH") or DEFAULT_BASELINE_PATH)
    summary = apply_baseline_comparison(analytics_path, markdown_path, baseline_path)
    print(json.dumps(summary["baseline_comparison"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
