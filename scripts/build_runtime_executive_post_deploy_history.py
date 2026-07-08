#!/usr/bin/env python3
"""Build Runtime Executive post-deploy temporal history.

The builder appends the latest post-deploy smoke signal to a bounded JSON
history and derives operational trends without requiring a database.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_HISTORY_CANDIDATES = [
    "docs/ops-dashboard/data/runtime-executive-post-deploy-history.json",
    "artifacts/runtime-executive-post-deploy-history/runtime-executive-post-deploy-history.json",
]

DEFAULT_SMOKE_CANDIDATES = [
    "artifacts/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke.json",
    "artifacts/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke.json",
    "audit/runtime/runtime-executive-post-deploy-smoke.json",
]


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


def resolve_existing(paths: list[str], root: Path) -> tuple[dict[str, Any], str | None]:
    for relative in paths:
        payload = load_json(root / relative)
        if payload:
            return payload, relative
    return {}, None


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_state(status: Any) -> str:
    value = str(status or "unknown").lower()
    if value in {"passed", "success", "healthy", "green", "ok", "true"}:
        return "green"
    if value in {"warning", "yellow", "degraded", "partial"}:
        return "yellow"
    if value in {"failed", "failure", "critical", "red", "blocked", "false"}:
        return "red"
    return "unknown"


def build_sample(smoke: dict[str, Any], *, source_artifact: str | None) -> dict[str, Any]:
    checks = smoke.get("checks") or {}
    page = checks.get("page") or {}
    contract = checks.get("contract") or {}
    failures = smoke.get("failures") or []
    state = normalize_state(smoke.get("status"))
    score = 100 if state == "green" else 65 if state == "yellow" else 0 if state == "red" else 40
    latencies = [value for value in (page.get("elapsed_ms"), contract.get("elapsed_ms")) if isinstance(value, (int, float))]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None

    return {
        "timestamp": smoke.get("validated_at") or iso_now(),
        "validated_at_epoch": int(smoke.get("validated_at_epoch") or time.time()),
        "state": state,
        "availability_percent": 100 if state == "green" else 50 if state == "yellow" else 0,
        "executive_score": score,
        "failure_count": len(failures),
        "failures": failures,
        "avg_latency_ms": avg_latency,
        "page_elapsed_ms": page.get("elapsed_ms"),
        "contract_elapsed_ms": contract.get("elapsed_ms"),
        "page_status_code": page.get("status_code"),
        "contract_status_code": contract.get("status_code"),
        "base_url": smoke.get("base_url"),
        "page_url": smoke.get("page_url"),
        "contract_url": smoke.get("contract_url"),
        "source_artifact": source_artifact or "missing",
    }


def sample_key(sample: dict[str, Any]) -> str:
    return "|".join(
        str(sample.get(key) or "")
        for key in ("validated_at_epoch", "base_url", "page_url", "contract_url", "state")
    )


def append_bounded(existing: list[dict[str, Any]], sample: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    items = list(existing)
    if sample_key(sample) not in {sample_key(item) for item in items}:
        items.append(sample)
    items.sort(key=lambda item: int(item.get("validated_at_epoch") or 0))
    return items[-limit:]


def trend(values: list[float | int | None], *, tolerance: float = 1.0, inverse: bool = False) -> str:
    series = [float(value) for value in values if isinstance(value, (int, float))]
    if len(series) < 2:
        return "stable"
    delta = series[-1] - series[0]
    if abs(delta) <= tolerance:
        return "stable"
    upward = delta > 0
    if inverse:
        upward = not upward
    return "up" if upward else "down"


def compute_mtbf(samples: list[dict[str, Any]]) -> float | None:
    failure_epochs = [int(item.get("validated_at_epoch") or 0) for item in samples if int(item.get("failure_count") or 0) > 0]
    if len(failure_epochs) < 2:
        return None
    deltas = [failure_epochs[index] - failure_epochs[index - 1] for index in range(1, len(failure_epochs))]
    return round(sum(deltas) / len(deltas) / 3600, 2) if deltas else None


def build_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "samples": 0,
            "availability_percent": 0,
            "avg_latency_ms": None,
            "max_latency_ms": None,
            "failure_count": 0,
            "score_trend": "stable",
            "latency_trend": "stable",
            "failure_trend": "stable",
            "mtbf_hours": None,
            "stability": "unknown",
        }
    availability = round(sum(float(item.get("availability_percent") or 0) for item in samples) / len(samples), 2)
    latencies = [float(item.get("avg_latency_ms")) for item in samples if isinstance(item.get("avg_latency_ms"), (int, float))]
    failures = [int(item.get("failure_count") or 0) for item in samples]
    scores = [int(item.get("executive_score") or 0) for item in samples]
    failure_total = sum(failures)
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
    max_latency = round(max(latencies), 2) if latencies else None
    score_trend = trend(scores, tolerance=2)
    latency_trend = trend(latencies, tolerance=20, inverse=True)
    failure_trend = trend(failures, tolerance=0.5, inverse=True)

    if availability >= 99 and failure_total == 0:
        stability = "green"
    elif availability >= 95 and failure_total <= max(1, len(samples) // 10):
        stability = "yellow"
    else:
        stability = "red"

    return {
        "samples": len(samples),
        "availability_percent": availability,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
        "failure_count": failure_total,
        "score_trend": score_trend,
        "latency_trend": latency_trend,
        "failure_trend": failure_trend,
        "mtbf_hours": compute_mtbf(samples),
        "stability": stability,
        "latest_state": samples[-1].get("state"),
        "latest_score": samples[-1].get("executive_score"),
        "latest_latency_ms": samples[-1].get("avg_latency_ms"),
    }


def enrich_brief(brief_path: Path, summary: dict[str, Any], history_path: str) -> None:
    brief = load_json(brief_path)
    if not brief:
        return
    estado = brief.setdefault("estado_unico", {})
    estado["runtime_executive_post_deploy_history"] = summary
    indicadores = brief.setdefault("indicadores_executivos", {})
    indicadores["runtime_executive_post_deploy_availability_percent"] = summary.get("availability_percent")
    indicadores["runtime_executive_post_deploy_avg_latency_ms"] = summary.get("avg_latency_ms")
    indicadores["runtime_executive_post_deploy_stability"] = summary.get("stability")
    links = brief.setdefault("links", {})
    links["runtime_executive_post_deploy_history"] = history_path
    write_json(brief_path, brief)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Runtime Executive Post-Deploy history")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", default="docs/ops-dashboard/data/runtime-executive-post-deploy-history.json")
    parser.add_argument("--artifact-output", default="artifacts/runtime-executive-post-deploy-history/runtime-executive-post-deploy-history.json")
    parser.add_argument("--executive-brief", default="docs/ops-dashboard/data/executive-brief.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--smoke", action="append", default=[])
    args = parser.parse_args()

    smoke, smoke_source = resolve_existing([*args.smoke, *DEFAULT_SMOKE_CANDIDATES], args.root)
    history, history_source = resolve_existing(DEFAULT_HISTORY_CANDIDATES, args.root)
    existing_samples = history.get("history") or []
    samples = list(existing_samples)
    if smoke:
        samples = append_bounded(samples, build_sample(smoke, source_artifact=smoke_source), args.limit)
    else:
        samples = samples[-args.limit:]

    summary = build_summary(samples)
    payload = {
        "schema_version": "1.0.0",
        "contract": "runtime-executive-post-deploy-history",
        "generated_at": iso_now(),
        "source_history": history_source,
        "source_smoke": smoke_source,
        "limit": args.limit,
        "summary": summary,
        "history": samples,
        "guardrails": [
            "append_only_bounded_json",
            "no_database_required",
            "offline_artifact_consolidation",
            "no_secret_required",
        ],
    }

    output = args.root / args.output
    artifact_output = args.root / args.artifact_output
    write_json(output, payload)
    write_json(artifact_output, payload)
    enrich_brief(args.root / args.executive_brief, summary, args.output)
    print(json.dumps({"status": "ok", "samples": len(samples), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
