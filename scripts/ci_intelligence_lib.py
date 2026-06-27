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


def _confidence_from_runs(runs_analyzed: int) -> str:
    if runs_analyzed >= 10:
        return "high"
    if runs_analyzed >= 3:
        return "medium"
    return "low"


def derive_maturity_signals(
    ci_report: dict[str, Any] | None = None,
    pr_evidence: dict[str, Any] | None = None,
    coordenador: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Map operational evidence sources to delivery maturity dimension overrides."""
    signals: dict[str, dict[str, Any]] = {}

    if ci_report:
        operational_score = float(ci_report.get("operational_score") or 0)
        instability = ci_report.get("instability") or {}
        instability_rate = float(instability.get("rate_percent") or 0)
        runs_analyzed = int(ci_report.get("runs_analyzed") or 0)
        matches_total = int(ci_report.get("matches_total") or 0)
        pareto = ci_report.get("pareto_failures") or {}
        top_causes = pareto.get("top_causes") or []
        categories = set(ci_report.get("categories") or {})
        rerun_blocked = bool((ci_report.get("rerun_assessment") or {}).get("blocked"))

        signals["técnico"] = {
            "current_percent": round(operational_score, 2),
            "confidence_level": _confidence_from_runs(runs_analyzed),
            "evidence_links": [
                "artifacts/operational-ci-intelligence/operational-ci-intelligence.json",
                ".github/workflows/operational-ci-intelligence.yml",
            ],
            "next_recommended_action": (
                ci_report.get("recommended_next_actions") or ["Manter monitoramento operacional."]
            )[0],
        }
        signals["operacional"] = {
            "current_percent": round(max(0.0, 100.0 - instability_rate), 2),
            "confidence_level": _confidence_from_runs(runs_analyzed),
            "evidence_links": ["data/operational-ci-history/instability-history.json"],
            "next_recommended_action": (
                f"Taxa de instabilidade em {instability_rate}% — "
                f"tendência {(ci_report.get('instability_history') or {}).get('trend', {}).get('direction', 'unknown')}."
            ),
        }
        security_penalty = 15 if "security" in categories else 0
        signals["segurança"] = {
            "current_percent": round(max(0.0, operational_score - security_penalty), 2),
            "confidence_level": "high" if security_penalty == 0 and runs_analyzed >= 5 else "medium",
            "evidence_links": ["config/failure-patterns.json"],
            "next_recommended_action": (
                "Revisar falhas de segurança no Pareto antes de promover."
                if security_penalty
                else "Sem sinais de segurança no Pareto recente."
            ),
        }
        evidence_score = min(100.0, 60.0 + (10 if matches_total == 0 else 20) + min(runs_analyzed * 2, 20))
        signals["evidência"] = {
            "current_percent": round(evidence_score, 2),
            "confidence_level": _confidence_from_runs(runs_analyzed),
            "evidence_links": ["artifacts/operational-ci-intelligence/operational-ci-intelligence.json"],
            "next_recommended_action": f"{matches_total} match(es) classificados em {runs_analyzed} run(s) recentes.",
        }
        signals["observabilidade"] = {
            "current_percent": round(min(100.0, 50.0 + runs_analyzed * 3), 2),
            "confidence_level": _confidence_from_runs(runs_analyzed),
            "evidence_links": ["docs/OPERATIONAL_INCREMENTOS_ROADMAP.md"],
            "next_recommended_action": (
                f"Pareto com {pareto.get('total_causes', 0)} causa(s); "
                f"top: {(top_causes[0].get('name') if top_causes else 'nenhuma')}."
            ),
        }
        governance_score = operational_score - (15 if rerun_blocked else 0)
        signals["governança"] = {
            "current_percent": round(max(0.0, governance_score), 2),
            "confidence_level": "high" if not rerun_blocked and runs_analyzed >= 5 else "medium",
            "evidence_links": ["AGENTS.md", "config/ci-failure-knowledge-base.json"],
            "next_recommended_action": (
                "Bloquear reruns em loop até causa raiz documentada."
                if rerun_blocked
                else "Política de rerun dentro dos limites operacionais."
            ),
        }

    if pr_evidence:
        gate = pr_evidence.get("gate") or {}
        gate_status = str(gate.get("status") or "unknown")
        pr = pr_evidence.get("pr") or {}
        head_sha = str(pr.get("head_sha") or "")
        evidence_links = [f"audit/pr-evidence-gate.json"]
        if head_sha:
            evidence_links.append(f"pr-evidence-gate-{head_sha}")

        if gate_status == "passed":
            signals["evidência"] = {
                **signals.get("evidência", {}),
                "current_percent": max(signals.get("evidência", {}).get("current_percent", 0), 92.0),
                "confidence_level": "high",
                "evidence_links": evidence_links,
                "next_recommended_action": "PR Evidence Gate aprovado para o SHA analisado.",
            }
            signals["técnico"] = {
                **signals.get("técnico", {}),
                "current_percent": max(signals.get("técnico", {}).get("current_percent", 0), 88.0),
                "confidence_level": "high",
                "evidence_links": evidence_links,
                "next_recommended_action": "Workflows obrigatórios concluídos com evidência anexada.",
            }
        elif gate_status == "failed":
            signals["evidência"] = {
                **signals.get("evidência", {}),
                "current_percent": min(signals.get("evidência", {}).get("current_percent", 100), 55.0),
                "confidence_level": "high",
                "evidence_links": evidence_links,
                "next_recommended_action": "Corrigir falhas do PR Evidence Gate antes de elevar maturidade.",
            }
            signals["técnico"] = {
                **signals.get("técnico", {}),
                "current_percent": min(signals.get("técnico", {}).get("current_percent", 100), 60.0),
                "confidence_level": "high",
                "evidence_links": evidence_links,
                "next_recommended_action": "Workflows obrigatórios com falha ou pendência no SHA.",
            }

    if coordenador:
        summary = coordenador.get("summary") or {}
        runtime_score = float(summary.get("runtime_score") or coordenador.get("runtime_score") or 0)
        maturity_level = str(summary.get("maturity_level") or coordenador.get("maturity_level") or "")
        global_state = str(coordenador.get("global_state") or summary.get("global_state") or "unknown")

        if runtime_score:
            signals["operacional"] = {
                **signals.get("operacional", {}),
                "current_percent": round(runtime_score, 2),
                "confidence_level": "high",
                "evidence_links": ["artifacts/coordenador-status-evidence/coordenador-status.json"],
                "next_recommended_action": f"Coordenador: estado global {global_state}, maturidade {maturity_level or 'n/d'}.",
            }
            signals["governança"] = {
                **signals.get("governança", {}),
                "current_percent": round(runtime_score, 2),
                "confidence_level": "high" if global_state == "green" else "medium",
                "evidence_links": ["artifacts/coordenador-status-evidence/coordenador-status.json"],
                "next_recommended_action": str(coordenador.get("decision") or "Validar coordenador-status consolidado."),
            }

    return signals


def build_maturity_snapshot(report: dict[str, Any], head_sha: str | None = None) -> dict[str, Any]:
    return {
        "snapshot_at_utc": report.get("generated_at"),
        "head_sha": head_sha,
        "continuous_score": report.get("continuous_score"),
        "average_current_percent": report.get("average_current_percent"),
        "average_gap_percent": report.get("average_gap_percent"),
        "lowest_dimension": report.get("lowest_dimension"),
        "sources": list((report.get("sources") or {}).keys()),
    }


def merge_maturity_history(existing: list[dict[str, Any]], snapshot: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
    merged = [item for item in existing if isinstance(item, dict)]
    merged.append(snapshot)
    merged.sort(key=lambda item: str(item.get("snapshot_at_utc", "")))
    return merged[-max_items:]


def calculate_maturity_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "status": "SEM_DADOS",
            "direction": "unknown",
            "delta_score": 0.0,
            "delta_gap": 0.0,
            "points": 0,
        }

    scores = [float(item.get("continuous_score") or item.get("average_current_percent") or 0) for item in history]
    gaps = [float(item.get("average_gap_percent") or 0) for item in history]
    delta_score = round(scores[-1] - scores[0], 2)
    delta_gap = round(gaps[-1] - gaps[0], 2)

    if delta_score > 3 or delta_gap < -3:
        direction = "melhorando"
    elif delta_score < -3 or delta_gap > 3:
        direction = "piorando"
    else:
        direction = "estavel"

    return {
        "status": "ATIVO",
        "direction": direction,
        "delta_score": delta_score,
        "delta_gap": delta_gap,
        "points": len(history),
        "first_score": scores[0],
        "last_score": scores[-1],
        "avg_score": round(sum(scores) / len(scores), 2),
        "avg_gap_percent": round(sum(gaps) / len(gaps), 2),
    }
