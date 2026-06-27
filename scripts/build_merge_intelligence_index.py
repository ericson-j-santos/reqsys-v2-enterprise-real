#!/usr/bin/env python3
"""Build Merge Intelligence Index for ReqSys.

Gera JSONs estaticos consumiveis pelo dashboard operacional, consolidando
sinais locais de risco de merge, priorizacao de lanes e recomendacao governada.

O script e deterministico e offline: nao acessa rede nem GitHub API.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_INDEX_OUTPUT = "docs/ops-dashboard/data/merge-intelligence-index.json"
DEFAULT_LANE_OUTPUT = "docs/ops-dashboard/data/merge-lane-priority.json"

LANE_WEIGHTS = {
    "runtime-governance": 94,
    "docs": 90,
    "tests": 78,
    "implementation": 66,
    "workflow": 48,
    "unknown": 55,
}

RISK_PENALTY = {
    "low": 0,
    "medium": 14,
    "high": 32,
    "blocked": 72,
    "unknown": 28,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_lane(paths: list[str], fallback: str = "unknown") -> str:
    if not paths:
        return fallback or "unknown"
    if all(path.startswith(("docs/", "artifacts/")) for path in paths):
        return "runtime-governance"
    if any(path.startswith(".github/workflows/") for path in paths):
        return "workflow"
    if all(path.startswith("tests/") or "/tests/" in path for path in paths):
        return "tests"
    return fallback if fallback not in {"unknown", ""} else "implementation"


def score_mergeability(report: dict[str, Any]) -> int:
    risk = str(report.get("risk") or "unknown")
    lane = str(report.get("lane") or resolve_lane(report.get("changed_paths") or []))
    base = LANE_WEIGHTS.get(lane, LANE_WEIGHTS["unknown"])
    penalty = RISK_PENALTY.get(risk, RISK_PENALTY["unknown"])
    blockers = len(report.get("blocking_reasons") or [])
    hotspots = len((report.get("signals") or {}).get("concurrent_hotspot_paths") or [])
    workflow_count = int((report.get("signals") or {}).get("workflow_change_count") or 0)
    score = base - penalty - blockers * 8 - hotspots * 5 - max(0, workflow_count - 1) * 6
    if report.get("parallel_safe") is True:
        score += 8
    return max(0, min(100, int(round(score))))


def recommendation_for(score: int, report: dict[str, Any]) -> str:
    risk = str(report.get("risk") or "unknown")
    if risk == "blocked" or score < 35:
        return "isolamento_obrigatorio"
    if score < 55:
        return "merge_serializado"
    if score < 75:
        return "aguardar_estabilizacao"
    if score < 88:
        return "rerun_recomendado"
    return "merge_imediato"


def hotspot_heatmap(report: dict[str, Any]) -> list[dict[str, Any]]:
    signals = report.get("signals") or {}
    critical_files = report.get("critical_files") or []
    concurrent = signals.get("concurrent_hotspot_paths") or []
    paths = sorted(set(critical_files + concurrent))
    rows = []
    for path in paths:
        rows.append({
            "path": path,
            "critical": path in critical_files,
            "concurrent": path in concurrent,
            "heat": 100 if path in concurrent else 72,
        })
    return rows


def build_index(conflict_report: dict[str, Any], overlap_report: dict[str, Any]) -> dict[str, Any]:
    available = bool(conflict_report)
    safe_report = conflict_report or {
        "risk": "unknown",
        "lane": "unknown",
        "parallel_safe": False,
        "blocking_reasons": ["conflict_risk_report_missing"],
        "changed_paths": [],
        "signals": {},
        "recommendation": "aguardar_estabilizacao",
    }
    lane = resolve_lane(safe_report.get("changed_paths") or [], str(safe_report.get("lane") or "unknown"))
    score = score_mergeability(safe_report)
    recommendation = recommendation_for(score, safe_report)
    heatmap = hotspot_heatmap(safe_report)
    overlapping_prs = overlap_report.get("overlapping_prs") or []
    queue_pressure = len(overlapping_prs)
    saturation = "high" if queue_pressure >= 3 else "medium" if queue_pressure else "low"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "source_available": available,
        "source_paths": {
            "conflict_risk_report": "artifacts/pr-conflict-guard/conflict-risk-report.json",
            "open_pr_overlap": "artifacts/pr-conflict-guard/open-pr-overlap.json",
        },
        "merge_intelligence": {
            "risk": safe_report.get("risk"),
            "lane": lane,
            "parallel_safe": bool(safe_report.get("parallel_safe")),
            "mergeability_score": score,
            "recommendation": recommendation,
            "blocking_reasons": safe_report.get("blocking_reasons") or [],
            "changed_path_count": len(safe_report.get("changed_paths") or []),
            "critical_file_count": len(safe_report.get("critical_files") or []),
            "queue_saturation": saturation,
            "queue_pressure": queue_pressure,
            "confidence": "high" if available else "low",
        },
        "trend": {
            "conflict_tendency": "rising" if queue_pressure >= 3 else "stable" if queue_pressure else "low",
            "rerun_recommended": recommendation in {"rerun_recomendado", "aguardar_estabilizacao"},
            "serial_merge_required": recommendation in {"merge_serializado", "isolamento_obrigatorio"},
        },
        "hotspot_heatmap": heatmap,
        "overlapping_prs": overlapping_prs,
        "links": {
            "actions": f"https://github.com/{REPO}/actions",
            "pulls": f"https://github.com/{REPO}/pulls",
            "conflict_guard": f"https://github.com/{REPO}/actions/workflows/pr-conflict-guard.yml",
            "merge_queue": f"https://github.com/{REPO}/actions/workflows/governed-merge-queue.yml",
        },
    }


def build_lane_priority(index: dict[str, Any]) -> dict[str, Any]:
    intelligence = index.get("merge_intelligence") or {}
    current_lane = intelligence.get("lane") or "unknown"
    current_score = int(intelligence.get("mergeability_score") or 0)
    lanes = []
    for lane, weight in sorted(LANE_WEIGHTS.items(), key=lambda item: item[1], reverse=True):
        score = weight
        if lane == current_lane:
            score = max(score, current_score)
        lanes.append({
            "lane": lane,
            "priority_score": score,
            "current_pr_lane": lane == current_lane,
            "parallelism": "safe" if score >= 80 else "controlled" if score >= 60 else "serial",
        })
    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": index.get("generated_at") or utc_now(),
        "ranking": lanes,
        "policy": {
            "merge_imediato": "score >= 88 e sem bloqueios",
            "rerun_recomendado": "75 <= score < 88",
            "aguardar_estabilizacao": "55 <= score < 75",
            "merge_serializado": "35 <= score < 55",
            "isolamento_obrigatorio": "score < 35 ou risk=blocked",
        },
    }


def write_outputs(index: dict[str, Any], lane_priority: dict[str, Any], index_output: str, lane_output: str) -> None:
    index_path = Path(index_output)
    lane_path = Path(lane_output)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    lane_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lane_path.write_text(json.dumps(lane_priority, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera Merge Intelligence Index para dashboard operacional.")
    parser.add_argument("--conflict-risk-report", default="artifacts/pr-conflict-guard/conflict-risk-report.json")
    parser.add_argument("--open-pr-overlap", default="artifacts/pr-conflict-guard/open-pr-overlap.json")
    parser.add_argument("--index-output", default=DEFAULT_INDEX_OUTPUT)
    parser.add_argument("--lane-output", default=DEFAULT_LANE_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conflict_report = load_json(Path(args.conflict_risk_report))
    overlap_report = load_json(Path(args.open_pr_overlap))
    index = build_index(conflict_report, overlap_report)
    lane_priority = build_lane_priority(index)
    write_outputs(index, lane_priority, args.index_output, args.lane_output)
    if args.json:
        print(json.dumps(index, indent=2, ensure_ascii=False))
    else:
        intelligence = index["merge_intelligence"]
        print(
            f"mergeability_score={intelligence['mergeability_score']} "
            f"recommendation={intelligence['recommendation']} output={args.index_output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
