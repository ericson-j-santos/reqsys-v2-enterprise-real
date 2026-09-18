#!/usr/bin/env python3
"""Smoke público e histórico do card comparativo DEV/STG/PROD do Advisor.

O fluxo é deliberadamente report-only: qualquer inconsistência gera REVIEW,
nunca altera readiness ou bloqueia produção automaticamente.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_public_smoke_comparison"
CARD_MARKER = "executive-promotion-advisor-public-smoke-comparison"
ENVIRONMENTS = ("dev", "stg", "prod")
MAX_SAMPLES_PER_ENV = 90


def _get_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ReqSys-Governed-Smoke/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def smoke_public(base_url: str, environment: str) -> dict[str, Any]:
    environment = environment.lower()
    if environment not in ENVIRONMENTS:
        raise ValueError(f"ambiente inválido: {environment}")

    base = base_url.rstrip("/")
    errors: list[str] = []
    payload: dict[str, Any] = {}

    try:
        html = _get_text(f"{base}/index.html")
        if CARD_MARKER not in html and CARD_KEY not in html:
            errors.append("card comparativo ausente no HTML público")
    except Exception as exc:  # smoke deve produzir evidência, não promover exceção
        errors.append(f"falha ao consultar index.html: {exc}")

    try:
        payload = json.loads(_get_text(f"{base}/data/runtime-executive-index.json"))
        card = payload.get("cards", {}).get(CARD_KEY)
        if not isinstance(card, dict):
            errors.append("contrato comparativo ausente no Runtime Executive Index")
        else:
            if card.get("mode") != "report-only":
                errors.append("mode deve ser report-only")
            if card.get("production_blocker") is not False:
                errors.append("production_blocker deve ser false")
            if card.get("human_approval_required") is not True:
                errors.append("human_approval_required deve ser true")
    except Exception as exc:
        errors.append(f"falha ao consultar contrato público: {exc}")

    passed = not errors
    return {
        "schema_version": 1,
        "environment": environment,
        "url": base,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "PUBLIC_COMPARATIVE_SMOKE_PASSED" if passed else "PUBLIC_COMPARATIVE_SMOKE_REVIEW",
        "passed": passed,
        "errors": errors,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def append_history(history: dict[str, Any] | None, sample: dict[str, Any]) -> dict[str, Any]:
    result = dict(history or {})
    result["schema_version"] = 1
    result["mode"] = "report-only"
    result["production_blocker"] = False
    result["human_approval_required"] = True
    environments = result.setdefault("environments", {})
    env = sample["environment"]
    current = environments.setdefault(env, {"entries": []})
    entries = list(current.get("entries", []))

    fingerprint = (sample.get("checked_at"), sample.get("url"), sample.get("status"))
    if not any((item.get("checked_at"), item.get("url"), item.get("status")) == fingerprint for item in entries):
        entries.append(sample)
    entries = entries[-MAX_SAMPLES_PER_ENV:]

    passed_count = sum(1 for item in entries if item.get("passed") is True)
    streak = 0
    for item in reversed(entries):
        if item.get("passed") is True:
            streak += 1
        else:
            break

    current["entries"] = entries
    current["summary"] = {
        "sample_count": len(entries),
        "pass_rate_percent": round((passed_count / len(entries)) * 100, 2) if entries else 0.0,
        "stable_streak": streak,
        "latest_status": entries[-1]["status"] if entries else "NO_DATA",
        "visual_consistency": "consistent" if entries and entries[-1].get("passed") else "review",
        "eligible_for_human_review": len(entries) >= 10 and streak >= 5 and passed_count / len(entries) >= 0.98,
        "production_blocker": False,
    }

    covered = [name for name in ENVIRONMENTS if environments.get(name, {}).get("entries")]
    result["summary"] = {
        "environment_count": len(covered),
        "covered_environments": covered,
        "coverage_complete": len(covered) == len(ENVIRONMENTS),
        "sample_count": sum(len(environments.get(name, {}).get("entries", [])) for name in ENVIRONMENTS),
    }
    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True, choices=ENVIRONMENTS)
    parser.add_argument("--url", required=True)
    parser.add_argument("--history", default="history.json")
    parser.add_argument("--evidence", default="evidence.json")
    args = parser.parse_args()

    history_path = Path(args.history)
    prior = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
    evidence = smoke_public(args.url, args.environment)
    updated = append_history(prior, evidence)

    Path(args.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    history_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(evidence["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
