#!/usr/bin/env python3
"""Shared CI Intelligence primitives: classification, Pareto ranking and instability history.

Dependency-free helpers used by operational_ci_intelligence.py and backend runtime services.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

SEVERITY_WEIGHT = {
    "critical": 100,
    "high": 80,
    "medium": 50,
    "low": 20,
    "info": 5,
}

BLOCKING_CONCLUSIONS = {"failure", "timed_out", "action_required"}


def normalize(value: Any) -> str:
    return str(value or "").lower()


def classify_kb(text: str, knowledge_base: dict[str, Any]) -> list[dict[str, Any]]:
    text_norm = normalize(text)
    matches: list[dict[str, Any]] = []
    for item in knowledge_base.get("known_failures", []):
        symptoms = item.get("symptoms", [])
        if any(normalize(symptom) in text_norm for symptom in symptoms):
            matches.append({**item, "source": "knowledge_base"})
    return matches


def classify_patterns(text: str, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    text_norm = normalize(text)
    matches: list[dict[str, Any]] = []
    for pattern in catalog.get("patterns", []):
        for token in pattern.get("match_any", []):
            if normalize(token) in text_norm:
                matches.append(
                    {
                        "id": pattern.get("id"),
                        "category": pattern.get("category", "unknown"),
                        "severity": pattern.get("severity", "info"),
                        "owner": pattern.get("owner", "ci_cd"),
                        "name": pattern.get("name"),
                        "recommended_action": pattern.get("recommended_action"),
                        "safe_rerun": bool(pattern.get("can_auto_rerun", False)),
                        "source": "failure_pattern_engine",
                    }
                )
                break
    return matches


def classify_text(text: str, knowledge_base: dict[str, Any], catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for match in classify_kb(text, knowledge_base):
        key = str(match.get("id") or match.get("category"))
        if key not in seen:
            seen.add(key)
            merged.append(match)
    if catalog:
        for match in classify_patterns(text, catalog):
            key = str(match.get("id") or match.get("category"))
            if key not in seen:
                seen.add(key)
                merged.append(match)
    return merged


def severity_weight(severity: str) -> int:
    return SEVERITY_WEIGHT.get(normalize(severity), 10)


def build_pareto_ranking(classified_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank failure causes by frequency × severity (Pareto 80/20)."""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "severity_score": 0, "runs": set(), "owner": "ci_cd", "sources": set()}
    )

    for run in classified_runs:
        run_id = str(run.get("run_id") or run.get("url") or "unknown")
        for match in run.get("matches", []):
            key = str(match.get("id") or match.get("category") or "unknown")
            bucket = buckets[key]
            bucket["id"] = key
            bucket["category"] = match.get("category", "unknown")
            bucket["severity"] = match.get("severity", "info")
            bucket["name"] = match.get("name") or match.get("probable_root_cause") or key
            bucket["owner"] = match.get("owner", bucket["owner"])
            bucket["count"] += 1
            bucket["severity_score"] += severity_weight(str(match.get("severity", "info")))
            bucket["runs"].add(run_id)
            bucket["sources"].add(str(match.get("source", "unknown")))

    items = []
    for key, bucket in buckets.items():
        impact = bucket["count"] * severity_weight(str(bucket["severity"]))
        items.append(
            {
                "id": key,
                "name": bucket["name"],
                "category": bucket["category"],
                "severity": bucket["severity"],
                "owner": bucket["owner"],
                "occurrences": bucket["count"],
                "affected_runs": len(bucket["runs"]),
                "impact_score": impact,
                "sources": sorted(bucket["sources"]),
            }
        )

    items.sort(key=lambda item: item["impact_score"], reverse=True)
    total_impact = sum(item["impact_score"] for item in items) or 1
    cumulative = 0.0
    for item in items:
        cumulative += (item["impact_score"] / total_impact) * 100
        item["cumulative_percent"] = round(cumulative, 2)
        item["pareto_tier"] = "A" if cumulative <= 80 else ("B" if cumulative <= 95 else "C")

    return {
        "total_causes": len(items),
        "total_impact": total_impact,
        "top_causes": items[:10],
        "pareto_threshold_80": [item for item in items if item["cumulative_percent"] <= 80 or item == items[0]],
    }


def compute_instability_rate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    if not total:
        return {"rate_percent": 0.0, "failed": 0, "unstable": 0, "total": 0}

    failed = sum(1 for run in runs if normalize(run.get("conclusion")) in BLOCKING_CONCLUSIONS)
    cancelled = sum(1 for run in runs if normalize(run.get("conclusion")) == "cancelled")
    unstable = failed + cancelled
    return {
        "rate_percent": round((unstable / total) * 100, 2),
        "failed": failed,
        "cancelled": cancelled,
        "unstable": unstable,
        "total": total,
    }


def build_instability_snapshot(report: dict[str, Any], instability: dict[str, Any], pareto: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "operational_score": report.get("operational_score"),
        "runs_analyzed": report.get("runs_analyzed"),
        "matches_total": report.get("matches_total"),
        "instability_rate_percent": instability.get("rate_percent", 0.0),
        "failed_runs": instability.get("failed", 0),
        "top_pareto_cause": pareto.get("top_causes", [{}])[0] if pareto.get("top_causes") else None,
        "pareto_causes_count": pareto.get("total_causes", 0),
    }


def merge_instability_history(existing: list[dict[str, Any]], snapshot: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
    merged = [item for item in existing if isinstance(item, dict)]
    merged.append(snapshot)
    merged.sort(key=lambda item: str(item.get("snapshot_at_utc", "")))
    return merged[-max_items:]


def calculate_instability_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "status": "SEM_DADOS",
            "direction": "unknown",
            "delta_instability": 0.0,
            "delta_score": 0.0,
            "points": 0,
        }

    instability_rates = [float(item.get("instability_rate_percent") or 0) for item in history]
    scores = [float(item.get("operational_score") or 0) for item in history]
    first_instability = instability_rates[0]
    last_instability = instability_rates[-1]
    delta_instability = round(last_instability - first_instability, 2)
    delta_score = round(scores[-1] - scores[0], 2)

    if delta_instability > 5 or delta_score < -5:
        direction = "piorando"
    elif delta_instability < -5 or delta_score > 5:
        direction = "melhorando"
    else:
        direction = "estavel"

    return {
        "status": history[-1].get("status", "SEM_DADOS"),
        "direction": direction,
        "delta_instability": delta_instability,
        "delta_score": delta_score,
        "points": len(history),
        "first_instability_rate": first_instability,
        "last_instability_rate": last_instability,
        "avg_instability_rate": round(sum(instability_rates) / len(instability_rates), 2),
        "avg_operational_score": round(sum(scores) / len(scores), 2),
    }
