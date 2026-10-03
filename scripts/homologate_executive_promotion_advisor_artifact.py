#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def check_public_url(url: str, timeout: float) -> dict[str, Any]:
    if not url:
        return {"observed": False, "status": "unknown", "http_status": None}
    try:
        request = Request(url, headers={"User-Agent": "reqsys-advisor-homologation/1.0"})
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            passed = response.status == 200 and "executive-promotion-advisor-card" in body
            return {
                "observed": True,
                "status": "passed" if passed else "failed",
                "http_status": response.status,
                "card_token_found": "executive-promotion-advisor-card" in body,
            }
    except Exception as exc:
        return {"observed": True, "status": "failed", "http_status": None, "error": str(exc)}


def homologate(root: Path, public_url: str = "", timeout: float = 10.0) -> dict[str, Any]:
    dashboard = root / "index.html"
    runtime_index = root / "data" / "runtime-executive-index.json"
    errors: list[str] = []

    if not dashboard.is_file():
        errors.append("dashboard_missing")
    if not runtime_index.is_file():
        errors.append("runtime_index_missing")

    card: dict[str, Any] = {}
    html = dashboard.read_text(encoding="utf-8") if dashboard.is_file() else ""
    if html.count('id="executive-promotion-advisor-card"') != 1:
        errors.append("advisor_card_invalid_count")

    if runtime_index.is_file():
        card = (load(runtime_index).get("cards") or {}).get("executive_promotion_advisor") or {}
        if not card:
            errors.append("advisor_contract_missing")
        if card.get("mode") != "report-only":
            errors.append("advisor_not_report_only")
        if card.get("production_blocker") is not False:
            errors.append("advisor_production_blocker_invalid")
        if card.get("human_approval_required") is not True:
            errors.append("advisor_human_gate_invalid")
        if card.get("decision") not in {"READY", "REVIEW", "HOLD"}:
            errors.append("advisor_decision_invalid")

    public = check_public_url(public_url, timeout)
    artifact_passed = not errors
    if public["observed"] and public["status"] == "failed":
        decision = "REVIEW"
    elif artifact_passed and public["status"] == "passed":
        decision = "HOMOLOGATED"
    elif artifact_passed:
        decision = "ARTIFACT_HOMOLOGATED_PUBLIC_PENDING"
    else:
        decision = "BLOCKED"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "decision": decision,
        "status": "passed" if artifact_passed else "failed",
        "production_blocker": False,
        "human_approval_required": True,
        "artifact": {
            "status": "passed" if artifact_passed else "failed",
            "card_present": html.count('id="executive-promotion-advisor-card"') == 1,
            "contract_present": bool(card),
            "advisor_decision": card.get("decision"),
        },
        "public_url": public,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--public-url", default="")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = homologate(args.root, args.public_url, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
