"""Classificação fail-closed de renovação preventiva do Pages Teams.

Este módulo nunca dispara workflows, publica Pages ou concede autorização.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "1.0.0"
LEAD_HOURS = 24.0
MAX_AGE_HOURS = 48.0


def assess(health: Any, *, now: datetime) -> dict[str, Any]:
    """Produz uma decisão reproduzível usando somente o monitor público real."""
    reason = "invalid_evidence"
    age: float | None = None

    if isinstance(health, dict):
        try:
            checked = datetime.fromisoformat(str(health["checked_at"]).replace("Z", "+00:00"))
            if checked.tzinfo is None:
                raise ValueError("timestamp_without_timezone")
            if now.tzinfo is None or not (0 <= (now - checked).total_seconds() <= 900):
                raise ValueError("outdated_monitor_evidence")
            if health.get("schema_version") != "1.1.0":
                raise ValueError("unexpected_health_schema")
            if health.get("state") != "healthy":
                raise ValueError("public_health_not_healthy")
            if health.get("http_status") != 200 or health.get("errors") != []:
                raise ValueError("public_health_not_clean")
            raw_age = health.get("data_age_hours")
            if isinstance(raw_age, bool) or not isinstance(raw_age, (int, float)):
                raise ValueError("invalid_data_age")
            age = float(raw_age)
            if not math.isfinite(age) or age < 0 or age > MAX_AGE_HOURS:
                raise ValueError("out_of_range_data_age")
        except (KeyError, TypeError, ValueError) as exc:
            reason = str(exc)
        else:
            reason = "lead_window_reached" if age >= LEAD_HOURS else "public_data_fresh"

    status = (
        "renewal_required" if reason == "lead_window_reached"
        else "fresh" if reason == "public_data_fresh"
        else "blocked"
    )
    return {
        "schema_version": SCHEMA,
        "contract": "reqsys-pages-teams-preexpiry-approval",
        "status": status,
        "reason": reason,
        "age_hours": age,
        "lead_hours": LEAD_HOURS,
        "maximum_age_hours": MAX_AGE_HOURS,
        "authorized_to_deploy": False,
        "dispatch_performed": False,
        "owner_action": "/reqsys run deploy-pages-current-main",
        "owner_action_issue": 1705,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = json.loads(args.health.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"health_evidence_unavailable: {exc}") from exc

    result = assess(evidence, now=datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with args.github_output.open("a", encoding="utf-8") as stream:
        stream.write(f"status={result['status']}\n")
        stream.write(f"age_hours={result['age_hours'] if result['age_hours'] is not None else 'n/a'}\n")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] == "renewal_required":
        print("::warning title=Pages refresh requires owner::Dashboard com idade >=24h; renovação exige autorização no gateway.")
    if result["status"] == "blocked":
        print(f"::warning title=Pages refresh policy blocked::{result['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
