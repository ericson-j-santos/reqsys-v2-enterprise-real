#!/usr/bin/env python3
"""Valida o card Executive Promotion Advisor em uma URL pública por ambiente."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCATION_DISCOVERY_CHECKS = (
    "dashboard_card_present",
    "render_hook_present",
    "contract_card_present",
)


def fetch_text(url: str, timeout: float = 15.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ReqSys-Advisor-Smoke/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def candidate_dashboard_bases(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    candidates = [base]
    ops_dashboard_suffix = "/docs/ops-dashboard"
    if not base.endswith(ops_dashboard_suffix):
        candidates.append(f"{base}{ops_dashboard_suffix}")
    return candidates


def smoke(base_url: str, environment: str, timeout: float = 15.0) -> dict[str, Any]:
    best_result: dict[str, Any] | None = None

    for candidate_base in candidate_dashboard_bases(base_url):
        dashboard_url = f"{candidate_base}/"
        contract_url = f"{candidate_base}/data/runtime-executive-index.json"
        errors: list[str] = []

        try:
            html = fetch_text(dashboard_url, timeout)
        except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
            html = ""
            errors.append(f"dashboard_unavailable: {exc}")

        try:
            contract = json.loads(fetch_text(contract_url, timeout))
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

        result = {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": environment,
            "base_url": candidate_base,
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
        if not errors:
            return result
        if all(checks[name] for name in LOCATION_DISCOVERY_CHECKS):
            return result
        if best_result is None or len(errors) < len(best_result["errors"]):
            best_result = result

    assert best_result is not None
    return best_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke público do Executive Promotion Advisor")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = smoke(args.base_url, args.environment, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
