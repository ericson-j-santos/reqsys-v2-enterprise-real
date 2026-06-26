#!/usr/bin/env python3
"""Generate static operations dashboard data.

Entrada principal: artifact/relatorio do Repository Health Watchdog.
Saida: JSON estatico consumido por docs/ops-dashboard/index.html.

Este script e deterministico e nao acessa rede.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _load_watchdog_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "overall_status": "unknown",
            "critical_failure_count": None,
            "warning_count": None,
            "results": [],
            "source_missing": True,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _score(report: dict[str, Any]) -> int:
    status = report.get("overall_status")
    critical = int(report.get("critical_failure_count") or 0)
    warnings = int(report.get("warning_count") or 0)
    if status == "passed":
        return 100
    if status == "warning":
        return max(60, 90 - warnings * 10)
    if status == "failed":
        return max(0, 50 - critical * 25 - warnings * 5)
    return 40


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_depth(runtime_report: dict[str, Any]) -> dict[str, Any]:
    depth = runtime_report.get("gold_standard_depth") or {}
    axes = depth.get("axes") or {}
    return {
        "available": bool(depth),
        "strategy": depth.get("strategy", ""),
        "overall_status": depth.get("overall_status", "unknown"),
        "overall_score": depth.get("overall_score"),
        "focus_order": depth.get("operational_focus_order", []),
        "axes": [
            {
                "id": axis_id,
                "status": axis.get("status"),
                "score": axis.get("score"),
                "operator_action": axis.get("operator_action"),
            }
            for axis_id, axis in axes.items()
        ],
    }


def build_dashboard_payload(report: dict[str, Any], repo: str, runtime_report: dict[str, Any] | None = None) -> dict[str, Any]:
    results = report.get("results", []) or []
    runtime_report = runtime_report or {}
    return {
        "schema_version": "1.0.0",
        "repo": repo or report.get("repo") or "unknown",
        "generated_at_epoch": int(time.time()),
        "overall_status": report.get("overall_status", "unknown"),
        "health_score": _score(report),
        "critical_failure_count": report.get("critical_failure_count"),
        "warning_count": report.get("warning_count"),
        "source_missing": report.get("source_missing", False),
        "checks": results,
        "links": {
            "actions": f"https://github.com/{repo}/actions" if repo else "",
            "pulls": f"https://github.com/{repo}/pulls" if repo else "",
            "main": f"https://github.com/{repo}/tree/main" if repo else "",
        },
        "runtime_gold_standard_depth": _runtime_depth(runtime_report),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys ops dashboard data")
    parser.add_argument("--watchdog-report", default="artifacts/repository-health-watchdog/repository-health-report.json")
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/health.json")
    parser.add_argument("--runtime-health-report", default="artifacts/runtime-health-center/runtime-health-report.json")
    args = parser.parse_args()

    report = _load_watchdog_report(Path(args.watchdog_report))
    runtime_report = _load_optional_json(Path(args.runtime_health_report))
    payload = build_dashboard_payload(report, args.repo, runtime_report)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
