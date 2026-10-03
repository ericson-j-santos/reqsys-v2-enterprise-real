#!/usr/bin/env python3
"""Generate operational SLO/SLA evidence from existing metrics artifacts.

Derives availability, CI success rate and MTTR SLOs from history and probes.
Report-only — no enforcement hooks.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SLO_DEFINITIONS = [
    {
        "slo_id": "ci_success_rate",
        "name": "Taxa de sucesso CI",
        "target_percent": 95.0,
        "window_days": 7,
        "metric_key": "ci_success_rate",
    },
    {
        "slo_id": "env_probe_availability",
        "name": "Disponibilidade probes multiambiente",
        "target_percent": 99.0,
        "window_days": 1,
        "metric_key": "env_availability",
    },
    {
        "slo_id": "mttr_minutes",
        "name": "MTTR operacional",
        "target_percent": 90.0,
        "window_days": 7,
        "metric_key": "mttr_slo",
        "max_minutes": 120,
    },
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def compute_ci_success_rate(history: list[dict[str, Any]]) -> float | None:
    if not history:
        return None
    latest = history[-1]
    failure_rate = float((latest.get("metrics") or {}).get("overall_failure_rate_percent") or 0)
    return round(100.0 - failure_rate, 2)


def compute_env_availability(multi_env: dict[str, Any]) -> float | None:
    environments = multi_env.get("environments") or []
    if not environments:
        return None
    remote = [e for e in environments if e.get("probe_available") and e.get("status") != "local_only"]
    if not remote:
        return None
    ready = sum(1 for e in remote if e.get("status") == "ready")
    return round((ready / len(remote)) * 100, 2)


def compute_mttr_slo_percent(history: list[dict[str, Any]], max_minutes: float) -> float | None:
    if not history:
        return None
    mttr = (history[-1].get("metrics") or {}).get("mttr_minutes")
    if mttr is None:
        return None
    mttr_val = float(mttr)
    if mttr_val <= 0:
        return 100.0
    if mttr_val >= max_minutes:
        return 0.0
    return round(max(0.0, 100.0 - (mttr_val / max_minutes) * 100), 2)


def build_slo_record(defn: dict[str, Any], actual: float | None, environment: str) -> dict[str, Any]:
    target = float(defn["target_percent"])
    if actual is None:
        return {
            "slo_id": defn["slo_id"],
            "name": defn["name"],
            "environment": environment,
            "target_percent": target,
            "window_days": defn["window_days"],
            "actual_percent": None,
            "error_budget_remaining": None,
            "breach": False,
            "status": "no_data",
        }
    error_budget = round(actual - target, 2)
    breach = actual < target
    return {
        "slo_id": defn["slo_id"],
        "name": defn["name"],
        "environment": environment,
        "target_percent": target,
        "window_days": defn["window_days"],
        "actual_percent": actual,
        "error_budget_remaining": error_budget,
        "breach": breach,
        "status": "breach" if breach else "met",
    }


def generate(
    history: list[dict[str, Any]],
    multi_env: dict[str, Any],
    commit_sha: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    ci_rate = compute_ci_success_rate(history)
    env_avail = compute_env_availability(multi_env)
    mttr_max = 120.0
    mttr_slo = compute_mttr_slo_percent(history, mttr_max)

    metric_values = {
        "ci_success_rate": ci_rate,
        "env_availability": env_avail,
        "mttr_slo": mttr_slo,
    }

    slos = []
    for defn in SLO_DEFINITIONS:
        actual = metric_values.get(defn["metric_key"])
        env = "all" if defn["metric_key"] != "env_availability" else "multi"
        slos.append(build_slo_record(defn, actual, env))

    breaches = sum(1 for s in slos if s.get("breach"))
    if breaches >= 2:
        status, risk = "degraded", "high"
    elif breaches == 1:
        status, risk = "watch", "medium"
    else:
        status, risk = "healthy", "low"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "operational-slo-evidence",
        "status": status,
        "confidence_level": "high" if history else "low",
        "maturity_percent": round(100 - breaches * 25, 2),
        "operational_risk": risk,
        "commit_sha": commit_sha,
        "correlation_id": correlation_id or str(uuid4()),
        "mode": "report_only",
        "summary": {
            "slo_count": len(slos),
            "breach_count": breaches,
            "met_count": sum(1 for s in slos if s.get("status") == "met"),
            "no_data_count": sum(1 for s in slos if s.get("status") == "no_data"),
        },
        "slos": slos,
        "guardrails": ["report_only", "no_auto_block", "human_review_on_breach"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate operational SLO evidence.")
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("artifacts/operational-history/operational-history.json"),
    )
    parser.add_argument(
        "--multi-env",
        type=Path,
        default=Path("artifacts/operational-multi-environment/multi-environment-evidence.json"),
    )
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-slo-evidence"))
    parser.add_argument("--dashboard-out", type=Path, default=Path("docs/ops-dashboard/data/slo-evidence.json"))
    args = parser.parse_args()

    history = load_json(args.history, [])
    if not isinstance(history, list):
        history = []
    multi_env = load_json(args.multi_env, {})
    report = generate(history, multi_env, args.commit_sha, args.correlation_id or None)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-slo-evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.dashboard_out.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"status={report['status']} breaches={report['summary']['breach_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
