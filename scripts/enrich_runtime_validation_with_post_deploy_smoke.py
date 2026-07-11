#!/usr/bin/env python3
"""Enrich Runtime Validation Consolidator outputs with post-deploy smoke evidence.

This adapter keeps the existing consolidator stable and injects the
Runtime Executive post-deploy smoke result into:

- runtime-validation-snapshot.json
- executive-brief.json

The script is offline/read-only and only transforms local artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SMOKE_CANDIDATES = [
    "artifacts/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke.json",
    "artifacts/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke.json",
    "audit/runtime/runtime-executive-post-deploy-smoke.json",
]


STATE_SCORE = {
    "green": 100,
    "yellow": 65,
    "red": 0,
    "unknown": 40,
}


STATE_RANK = {
    "green": 0,
    "yellow": 1,
    "unknown": 1,
    "red": 2,
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_smoke(candidates: list[str], root: Path) -> tuple[dict[str, Any], str | None]:
    for candidate in candidates:
        path = root / candidate
        payload = load_json(path)
        if payload:
            return payload, candidate
    return {}, None


def normalize_state(status: Any, *, available: bool) -> str:
    if not available:
        return "unknown"
    normalized = str(status or "unknown").lower()
    if normalized in {"passed", "success", "healthy", "green", "ok", "true"}:
        return "green"
    if normalized in {"failed", "failure", "critical", "red", "blocked", "false"}:
        return "red"
    if normalized in {"warning", "yellow", "degraded", "partial"}:
        return "yellow"
    return "unknown"


def merge_state(*states: str) -> str:
    ranked = sorted(states, key=lambda item: STATE_RANK.get(item, 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def evaluate_smoke(smoke: dict[str, Any], source_path: str | None) -> dict[str, Any]:
    available = bool(smoke)
    state = normalize_state(smoke.get("status"), available=available)
    failures = smoke.get("failures") or []
    checks = smoke.get("checks") or {}
    page = checks.get("page") or {}
    contract = checks.get("contract") or {}
    score = 100 if state == "green" else 65 if state == "yellow" else 0 if state == "red" else 40

    return {
        "id": "runtime_executive_post_deploy",
        "label": "Runtime Executive Post-Deploy Smoke",
        "state": state,
        "score": score,
        "available": available,
        "detail": "endpoint público validado" if state == "green" else f"failures={len(failures)}",
        "base_url": smoke.get("base_url"),
        "page_url": smoke.get("page_url"),
        "contract_url": smoke.get("contract_url"),
        "failure_count": len(failures),
        "failures": failures,
        "page_status_code": page.get("status_code"),
        "contract_status_code": contract.get("status_code"),
        "page_elapsed_ms": page.get("elapsed_ms"),
        "contract_elapsed_ms": contract.get("elapsed_ms"),
        "source_artifact": source_path or "missing",
    }


def recompute_score(domains: dict[str, dict[str, Any]], current_score: int) -> int:
    post = domains.get("runtime_executive_post_deploy") or {}
    if not post.get("available"):
        return current_score
    # O smoke pós-deploy é um sinal de produção real, mas não deve dominar os
    # demais sinais. Peso incremental: 12% do score final.
    return round((current_score * 0.88) + (int(post.get("score") or 0) * 0.12))


def recompute_gold(snapshot: dict[str, Any]) -> None:
    gold = snapshot.get("gold_standard_operational_risk") or {}
    domain = (snapshot.get("domains") or {}).get("runtime_executive_post_deploy") or {}
    if not gold or not domain.get("available"):
        return

    current = int(gold.get("overall_score") or 0)
    if domain.get("state") == "green":
        current = min(100, current + 3)
    elif domain.get("state") == "red":
        current = max(0, current - 8)
    gold["overall_score"] = current
    gold["remaining_gap"] = max(0, int(gold.get("target_percent") or 100) - current)
    gold["runtime_executive_post_deploy_state"] = domain.get("state")
    gold["status"] = "gold" if current >= 95 and gold["remaining_gap"] <= 5 else "consolidating" if current >= 75 else "evolving"


def enrich_snapshot(snapshot: dict[str, Any], post_domain: dict[str, Any]) -> dict[str, Any]:
    domains = snapshot.setdefault("domains", {})
    domains["runtime_executive_post_deploy"] = post_domain

    current_score = int(snapshot.get("validation_score") or 0)
    new_score = recompute_score(domains, current_score)
    snapshot["validation_score"] = new_score
    snapshot["operational_risk_percent"] = max(0, min(100, 100 - new_score))
    snapshot["confidence_percent"] = max(0, 100 - snapshot["operational_risk_percent"])
    snapshot["overall_state"] = merge_state(*(domain.get("state", "unknown") for domain in domains.values()))
    snapshot["runtime_executive_post_deploy_ready"] = post_domain.get("state") == "green"
    snapshot["public_endpoint_ready"] = post_domain.get("state") == "green"

    blockers = set(snapshot.get("blockers") or [])
    blockers.discard("runtime_executive_post_deploy_failed")
    if post_domain.get("available") and post_domain.get("state") == "red":
        blockers.add("runtime_executive_post_deploy_failed")
    snapshot["blockers"] = sorted(blockers)

    recompute_gold(snapshot)
    gold = snapshot.get("gold_standard_operational_risk") or {}
    snapshot["production_ready"] = bool(
        gold.get("overall_score", 0) >= 95
        and snapshot.get("overall_state") == "green"
        and not snapshot.get("blockers")
        and snapshot.get("runtime_executive_post_deploy_ready")
    )

    sources = snapshot.setdefault("sources", {})
    sources["runtime_executive_post_deploy_smoke"] = {
        "available": post_domain.get("available", False),
        "path": post_domain.get("source_artifact"),
        "candidates": DEFAULT_SMOKE_CANDIDATES,
    }

    guardrails = snapshot.setdefault("guardrails", {})
    guardrails["post_deploy_runtime_executive_smoke_integrated"] = True
    return snapshot


def append_unique(values: list[Any], value: str) -> list[Any]:
    return values if value in values else [*values, value]


def enrich_brief(brief: dict[str, Any], post_domain: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    state = post_domain.get("state")
    semaforo = brief.setdefault("semaforo_executivo", {})
    semaforo["runtime_executive_publico"] = "green" if state == "green" else "red" if state == "red" else "yellow"
    semaforo["deploy"] = "green" if state == "green" else "red" if state == "red" else semaforo.get("deploy", "yellow")

    indicadores = brief.setdefault("indicadores_executivos", {})
    indicadores["runtime_executive_post_deploy_percent"] = int(post_domain.get("score") or 0)
    indicadores["progresso_tecnico_percent"] = snapshot.get("validation_score", indicadores.get("progresso_tecnico_percent", 0))
    indicadores["risco_operacional_percent"] = snapshot.get("operational_risk_percent", indicadores.get("risco_operacional_percent", 100))
    indicadores["confianca_percent"] = snapshot.get("confidence_percent", indicadores.get("confianca_percent", 0))
    indicadores["producao_percent"] = (snapshot.get("gold_standard_operational_risk") or {}).get(
        "overall_score",
        indicadores.get("producao_percent", 0),
    )

    estado = brief.setdefault("estado_unico", {})
    estado["validado"] = append_unique(estado.get("validado", []), "runtime_executive_post_deploy_smoke")
    if post_domain.get("state") == "green":
        estado["evidenciado"] = append_unique(estado.get("evidenciado", []), "endpoint_publico_runtime_executive")
        estado["consolidado"] = append_unique(estado.get("consolidado", []), "runtime_executive_publico_real")
    else:
        estado["evidenciado"] = append_unique(estado.get("evidenciado", []), "endpoint_publico_runtime_executive_pendente")
    estado["runtime_executive_post_deploy"] = {
        "state": post_domain.get("state"),
        "score": post_domain.get("score"),
        "page_url": post_domain.get("page_url"),
        "contract_url": post_domain.get("contract_url"),
        "failure_count": post_domain.get("failure_count"),
    }
    estado["pronto_para_producao"] = bool(snapshot.get("production_ready"))

    links = brief.setdefault("links", {})
    if post_domain.get("page_url"):
        links["runtime_executive_public_page"] = post_domain["page_url"]
    if post_domain.get("contract_url"):
        links["runtime_executive_public_contract"] = post_domain["contract_url"]

    brief["proximo_incremento_seguro"] = (
        "manter_monitoramento_pos_deploy_runtime_executive" if state == "green"
        else "corrigir_runtime_executive_public_endpoint_e_reexecutar_smoke"
    )
    return brief


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich Runtime Validation outputs with Runtime Executive post-deploy smoke")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--snapshot", type=Path, default=Path("artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json"))
    parser.add_argument("--executive-brief", type=Path, default=Path("docs/ops-dashboard/data/executive-brief.json"))
    parser.add_argument("--smoke", action="append", default=[], help="Additional smoke artifact candidate path")
    args = parser.parse_args()

    candidates = [*args.smoke, *DEFAULT_SMOKE_CANDIDATES]
    smoke, source_path = resolve_smoke(candidates, args.root)
    post_domain = evaluate_smoke(smoke, source_path)

    snapshot_path = args.root / args.snapshot
    brief_path = args.root / args.executive_brief
    snapshot = load_json(snapshot_path)
    brief = load_json(brief_path)
    if not snapshot:
        raise SystemExit(f"snapshot ausente ou vazio: {snapshot_path}")
    if not brief:
        raise SystemExit(f"executive brief ausente ou vazio: {brief_path}")

    snapshot = enrich_snapshot(snapshot, post_domain)
    brief = enrich_brief(brief, post_domain, snapshot)
    write_json(snapshot_path, snapshot)
    write_json(brief_path, brief)

    print(json.dumps({
        "status": "enriched",
        "post_deploy_state": post_domain.get("state"),
        "post_deploy_available": post_domain.get("available"),
        "snapshot": str(snapshot_path),
        "executive_brief": str(brief_path),
        "source_artifact": post_domain.get("source_artifact"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
