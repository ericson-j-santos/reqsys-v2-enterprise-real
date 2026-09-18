#!/usr/bin/env python3
"""Executive Predictive Stability Layer for ReqSys.

Consumes the GitHub Actions History Lake JSONL dataset and produces governed
predictive stability indicators without external services, secrets, deploys or
production mutation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

BLOCKING_FAILURES = {"failure", "timed_out", "action_required"}
WINDOW_SIZE = 30


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return sorted(records, key=lambda row: str(row.get("created_at") or ""))


def health(row: dict[str, Any]) -> str:
    if row.get("status") != "completed":
        return "pending"
    conclusion = row.get("conclusion")
    if conclusion == "success":
        return "success"
    if conclusion in BLOCKING_FAILURES:
        return "blocking_failure"
    return "non_blocking"


def pct(part: float, total: float) -> float:
    return round((part / total) * 100, 2) if total else 0.0


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def split_windows(records: list[dict[str, Any]], size: int = WINDOW_SIZE) -> list[list[dict[str, Any]]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def window_failure_rates(records: list[dict[str, Any]]) -> list[float]:
    rates: list[float] = []
    for window in split_windows(records):
        completed = [row for row in window if row.get("status") == "completed"]
        failures = [row for row in completed if health(row) == "blocking_failure"]
        rates.append(pct(len(failures), len(completed)))
    return rates


def trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "INSUFFICIENT_HISTORY"
    delta = values[-1] - values[0]
    if delta >= 5:
        return "DEGRADING"
    if delta <= -5:
        return "IMPROVING"
    return "STABLE"


def workflow_degradation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_workflow[str(row.get("workflow_name") or "unknown")].append(row)
    findings: list[dict[str, Any]] = []
    for name, rows in by_workflow.items():
        completed = [row for row in rows if row.get("status") == "completed"]
        failures = [row for row in completed if health(row) == "blocking_failure"]
        durations = [int(row["duration_seconds"]) for row in completed if isinstance(row.get("duration_seconds"), int)]
        failure_rate = pct(len(failures), len(completed))
        duration_volatility = round(pstdev(durations), 2) if len(durations) > 1 else 0.0
        risk = clamp((failure_rate * 0.7) + min(duration_volatility / 60, 20) * 0.3)
        if risk >= 5 or failure_rate > 0:
            findings.append(
                {
                    "workflow_name": name,
                    "records": len(rows),
                    "completed": len(completed),
                    "blocking_failures": len(failures),
                    "failure_rate_percent": failure_rate,
                    "duration_volatility_seconds": duration_volatility,
                    "degradation_risk_percent": risk,
                }
            )
    return sorted(findings, key=lambda row: row["degradation_risk_percent"], reverse=True)


def build_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    completed = [row for row in records if row.get("status") == "completed"]
    successful = [row for row in completed if health(row) == "success"]
    failures = [row for row in completed if health(row) == "blocking_failure"]
    pending = [row for row in records if health(row) == "pending"]
    rates = window_failure_rates(records)
    trend = trend_direction(rates)
    degradation = workflow_degradation(records)
    durations = [int(row["duration_seconds"]) for row in completed if isinstance(row.get("duration_seconds"), int)]
    event_mix = Counter(str(row.get("event") or "unknown") for row in records)

    failure_rate = pct(len(failures), len(completed))
    success_rate = pct(len(successful), len(completed))
    volatility_penalty = min((pstdev(durations) / 120) if len(durations) > 1 else 0, 8)
    history_penalty = 10 if total < 30 else 4 if total < 100 else 0
    degradation_penalty = min(sum(item["degradation_risk_percent"] for item in degradation[:5]) / 5, 10) if degradation else 0
    pending_penalty = min(len(pending) * 0.15, 5)

    predicted_risk = clamp(failure_rate + volatility_penalty + history_penalty + degradation_penalty + pending_penalty)
    stability_score = clamp(100 - predicted_risk)
    confidence = clamp(88 + min(total / 20, 8) - history_penalty - min(volatility_penalty / 2, 4))
    precision = clamp(100 - predicted_risk + min(confidence - 90, 5) * 0.2, 0, 99.9)

    readiness = "PREDICTIVE_STABILITY_READY"
    if total < 30:
        readiness = "PREDICTIVE_STABILITY_WARMING_UP"
    elif predicted_risk > 5:
        readiness = "PREDICTIVE_STABILITY_WATCH"

    return {
        "generated_at": utc_now(),
        "readiness_state": readiness,
        "total_records": total,
        "completed_records": len(completed),
        "success_rate_percent": success_rate,
        "blocking_failure_rate_percent": failure_rate,
        "predicted_risk_percent": predicted_risk,
        "predictive_precision_percent": precision,
        "confidence_percent": confidence,
        "stability_score": stability_score,
        "failure_trend_direction": trend,
        "window_failure_rates_percent": rates,
        "average_duration_seconds": round(mean(durations), 2) if durations else 0.0,
        "duration_volatility_seconds": round(pstdev(durations), 2) if len(durations) > 1 else 0.0,
        "event_mix": dict(event_mix),
        "workflow_degradation_findings": degradation[:20],
        "governance": {
            "external_write": "disabled",
            "deployment": "disabled",
            "secrets_change": "disabled",
            "human_review_required": True,
            "source": "data/operational/github-actions-history/runs.jsonl",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Executive Predictive Stability Layer",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        "## Critical indicators",
        "",
        f"- Readiness: `{report['readiness_state']}`",
        f"- Predictive precision: `{report['predictive_precision_percent']}%`",
        f"- Confidence: `{report['confidence_percent']}%`",
        f"- Predicted risk: `{report['predicted_risk_percent']}%`",
        f"- Stability score: `{report['stability_score']}/100`",
        f"- Failure trend: `{report['failure_trend_direction']}`",
        "",
        "## Degradation findings",
        "",
    ]
    findings = report.get("workflow_degradation_findings") or []
    if not findings:
        lines.append("- No relevant degradation detected.")
    for item in findings[:10]:
        lines.append(
            f"- `{item['workflow_name']}`: risk `{item['degradation_risk_percent']}%`, "
            f"failure rate `{item['failure_rate_percent']}%`, failures `{item['blocking_failures']}`"
        )
    return "\n".join(lines) + "\n"


def render_html(report: dict[str, Any]) -> str:
    rows = []
    for item in report.get("workflow_degradation_findings", [])[:20]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item['workflow_name']))}</td>"
            f"<td>{item['degradation_risk_percent']}%</td>"
            f"<td>{item['failure_rate_percent']}%</td>"
            f"<td>{item['blocking_failures']}</td>"
            f"<td>{item['duration_volatility_seconds']}s</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ReqSys Executive Predictive Stability Layer</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 12px; padding: 16px; background: #f9fafb; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>ReqSys Executive Predictive Stability Layer</h1>
  <p>Gerado em UTC: <strong>{escape(report['generated_at'])}</strong></p>
  <div class=\"grid\">
    <div class=\"card\"><strong>Readiness</strong><br>{escape(report['readiness_state'])}</div>
    <div class=\"card\"><strong>Predictive precision</strong><br>{report['predictive_precision_percent']}%</div>
    <div class=\"card\"><strong>Confidence</strong><br>{report['confidence_percent']}%</div>
    <div class=\"card\"><strong>Predicted risk</strong><br>{report['predicted_risk_percent']}%</div>
    <div class=\"card\"><strong>Stability score</strong><br>{report['stability_score']}/100</div>
    <div class=\"card\"><strong>Failure trend</strong><br>{escape(report['failure_trend_direction'])}</div>
  </div>
  <h2>Workflow degradation findings</h2>
  <table>
    <thead><tr><th>Workflow</th><th>Risk</th><th>Failure rate</th><th>Failures</th><th>Volatility</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "executive-predictive-stability.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(render_markdown(report), encoding="utf-8")
    (output_dir / "executive-predictive-stability.html").write_text(render_html(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build executive predictive stability indicators.")
    parser.add_argument("--data-path", default="data/operational/github-actions-history/runs.jsonl")
    parser.add_argument("--output-dir", default="artifacts/executive-predictive-stability")
    parser.add_argument("--min-confidence", type=float, default=90.0)
    parser.add_argument("--max-risk", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(read_jsonl(Path(args.data_path)))
    write_artifacts(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["confidence_percent"] < args.min_confidence:
        return 1
    if report["predicted_risk_percent"] > args.max_risk:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
