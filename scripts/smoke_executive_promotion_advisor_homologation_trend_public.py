#!/usr/bin/env python3
"""Executa smoke público do card de tendência do Executive Promotion Advisor.

O smoke é estritamente report-only e nunca promove produção automaticamente.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

CARD_MARKER = 'id="executive-promotion-advisor-homologation-trend-card"'
RENDER_HOOK = "renderExecutivePromotionAdvisorHomologationTrend(payload);"
CARD_KEY = "executive_promotion_advisor_homologation_trend"
ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}


def fetch_text(url: str, timeout: float) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "ReqSys-Advisor-Public-Smoke/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL governada pelo workflow
        return int(response.status), response.read().decode("utf-8", errors="replace")


def build_evidence(environment: str, public_url: str, timeout: float = 15.0) -> dict[str, Any]:
    environment = environment.lower().strip()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError(f"ambiente inválido: {environment}")
    if not public_url.startswith(("https://", "http://")):
        raise ValueError("public_url deve usar http ou https")

    root = public_url.rstrip("/") + "/"
    index_url = urljoin(root, "index.html")
    runtime_url = urljoin(root, "data/runtime-executive-index.json")
    checks: dict[str, Any] = {
        "index_status": None,
        "runtime_status": None,
        "card_present": False,
        "render_hook_present": False,
        "contract_present": False,
        "mode_report_only": False,
        "production_blocker_false": False,
        "human_approval_required": False,
        "eligibility_boolean": False,
    }
    errors: list[str] = []
    card: dict[str, Any] = {}

    try:
        status, html = fetch_text(index_url, timeout)
        checks["index_status"] = status
        checks["card_present"] = CARD_MARKER in html
        checks["render_hook_present"] = RENDER_HOOK in html
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        errors.append(f"index_fetch_failed:{type(exc).__name__}")

    try:
        status, raw = fetch_text(runtime_url, timeout)
        checks["runtime_status"] = status
        payload = json.loads(raw)
        candidate = (payload.get("cards") or {}).get(CARD_KEY)
        if isinstance(candidate, dict):
            card = candidate
            checks["contract_present"] = True
            checks["mode_report_only"] = card.get("mode") == "report-only"
            checks["production_blocker_false"] = card.get("production_blocker") is False
            checks["human_approval_required"] = card.get("human_approval_required") is True
            checks["eligibility_boolean"] = isinstance(card.get("eligible_for_gate_review"), bool)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"runtime_fetch_failed:{type(exc).__name__}")

    required = (
        "card_present",
        "render_hook_present",
        "contract_present",
        "mode_report_only",
        "production_blocker_false",
        "human_approval_required",
        "eligibility_boolean",
    )
    passed = not errors and all(checks[name] for name in required)
    decision = "PUBLIC_SMOKE_PASSED" if passed else "PUBLIC_SMOKE_REVIEW"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "public_url": root,
        "index_url": index_url,
        "runtime_url": runtime_url,
        "status": "passed" if passed else "review",
        "decision": decision,
        "checks": checks,
        "advisor_trend": {
            "available": bool(card),
            "trend": card.get("trend"),
            "sample_count": card.get("sample_count"),
            "full_homologation_rate_percent": card.get("full_homologation_rate_percent"),
            "stable_streak": card.get("stable_streak"),
            "eligible_for_gate_review": card.get("eligible_for_gate_review", False),
        },
        "errors": errors,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke público da tendência do Advisor")
    parser.add_argument("--environment", required=True, choices=sorted(ALLOWED_ENVIRONMENTS))
    parser.add_argument("--public-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    evidence = build_evidence(args.environment, args.public_url, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "environment": evidence["environment"],
        "status": evidence["status"],
        "decision": evidence["decision"],
        "production_blocker": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
