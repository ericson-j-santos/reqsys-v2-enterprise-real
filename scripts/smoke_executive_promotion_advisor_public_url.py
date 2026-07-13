#!/usr/bin/env python3
"""Valida o card Executive Promotion Advisor em uma URL pública por ambiente."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def fetch_text(
    url: str,
    timeout: float = 15.0,
    attempts: int = 1,
    retry_delay: float = 0.0,
) -> str:
    """Obtém texto HTTP com repetição limitada para propagação eventual do Pages."""
    if attempts < 1:
        raise ValueError("attempts deve ser maior ou igual a 1")
    if retry_delay < 0:
        raise ValueError("retry_delay não pode ser negativo")

    request = urllib.request.Request(url, headers={"User-Agent": "ReqSys-Advisor-Smoke/1.0"})
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(retry_delay)

    raise RuntimeError(f"Falha inesperada ao consultar {url}: {last_error}")


def fetch_first(
    urls: Iterable[str],
    timeout: float = 15.0,
    attempts: int = 1,
    retry_delay: float = 0.0,
) -> tuple[str, str]:
    """Retorna o primeiro recurso público disponível e a URL efetivamente usada."""
    failures: list[str] = []
    for url in urls:
        try:
            return fetch_text(url, timeout, attempts, retry_delay), url
        except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
            failures.append(f"{url}: {exc}")

    raise urllib.error.URLError("; ".join(failures))


def public_candidates(base: str, environment: str) -> tuple[list[str], list[str]]:
    """Resolve caminhos públicos por ambiente, preservando fallback compatível."""
    if environment == "github-pages":
        return (
            [f"{base}/ops-dashboard/", f"{base}/"],
            [
                f"{base}/ops-dashboard/data/runtime-executive-index.json",
                f"{base}/data/runtime-executive-index.json",
            ],
        )

    return (
        [f"{base}/"],
        [f"{base}/data/runtime-executive-index.json"],
    )


def smoke(
    base_url: str,
    environment: str,
    timeout: float = 15.0,
    attempts: int = 12,
    retry_delay: float = 10.0,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    dashboard_candidates, contract_candidates = public_candidates(base, environment)
    errors: list[str] = []
    dashboard_url: str | None = None
    contract_url: str | None = None

    try:
        html, dashboard_url = fetch_first(dashboard_candidates, timeout, attempts, retry_delay)
    except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
        html = ""
        errors.append(f"dashboard_unavailable: {exc}")

    try:
        contract_text, contract_url = fetch_first(contract_candidates, timeout, attempts, retry_delay)
        contract = json.loads(contract_text)
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        contract = {}
        errors.append(f"contract_unavailable: {exc}")

    card = ((contract.get("cards") or {}).get("executive_promotion_advisor") or {}) if isinstance(contract, dict) else {}
    checks = {
        "dashboard_card_present": 'id="executive-promotion-advisor-card"' in html,
        "render_hook_present": "renderExecutivePromotionAdvisor(payload);" in html,
        "contract_card_present": bool(card),
        "report_only": card.get("mode") == "report-only",
        "production_blocker_disabled": card.get("production_blocker") is False,
        "human_approval_required": card.get("human_approval_required") is True,
    }
    errors.extend(name for name, passed in checks.items() if not passed)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "base_url": base,
        "resolved_urls": {
            "dashboard": dashboard_url,
            "contract": contract_url,
        },
        "status": "passed" if not errors else "failed",
        "decision": "HOMOLOGATED" if not errors else "BLOCKED",
        "checks": checks,
        "advisor": {
            "decision": card.get("decision"),
            "confidence_percent": card.get("confidence_percent"),
            "risk_domains": card.get("risk_domains") or [],
            "mode": card.get("mode"),
            "production_blocker": card.get("production_blocker"),
            "human_approval_required": card.get("human_approval_required"),
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke público do Executive Promotion Advisor")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = smoke(
        args.base_url,
        args.environment,
        args.timeout,
        args.attempts,
        args.retry_delay,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
