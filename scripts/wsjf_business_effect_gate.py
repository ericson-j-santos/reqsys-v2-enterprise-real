#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate(data: dict[str, Any], *, now: datetime | None = None, max_age_hours: int = 24) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    blockers: list[str] = []

    if data.get("environment") != "dev":
        blockers.append("environment_must_be_dev")
    if data.get("real") is not True:
        blockers.append("real_evidence_required")
    if data.get("mocked") is True or data.get("simulated") is True:
        blockers.append("mocked_evidence_forbidden")

    planner_task_id = str(data.get("planner_task_id") or "").strip()
    excel_task_id = str(data.get("excel_task_id") or "").strip()
    if not planner_task_id:
        blockers.append("planner_task_id_missing")
    if not excel_task_id:
        blockers.append("excel_task_id_missing")
    if planner_task_id and excel_task_id and planner_task_id != excel_task_id:
        blockers.append("planner_excel_task_id_mismatch")

    if data.get("excel_matching_rows") != 1:
        blockers.append("excel_row_must_be_unique")
    if data.get("local_fields_preserved") is not True:
        blockers.append("local_fields_not_proven_preserved")
    if data.get("planner_writeback_detected") is not False:
        blockers.append("planner_writeback_must_be_absent")

    source_run_url = str(data.get("source_run_url") or "").strip()
    if not source_run_url.startswith("https://github.com/"):
        blockers.append("source_run_url_missing_or_invalid")

    captured_at_raw = str(data.get("captured_at") or "").strip()
    if not captured_at_raw:
        blockers.append("captured_at_missing")
    else:
        try:
            captured_at = _parse_utc(captured_at_raw)
            if captured_at > now + timedelta(minutes=5):
                blockers.append("captured_at_in_future")
            elif now - captured_at > timedelta(hours=max_age_hours):
                blockers.append("evidence_stale")
        except ValueError:
            blockers.append("captured_at_invalid")

    passed = not blockers
    return {
        "status": "passed" if passed else "blocked",
        "real": passed,
        "mocked": False,
        "check": "wsjf_planner_excel_business_effect",
        "blocking_issues": blockers,
        "evidence": source_run_url or None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida efeito de negócio real Planner → Excel do WSJF")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args()

    if not args.evidence.exists():
        result = {
            "status": "blocked",
            "real": False,
            "mocked": False,
            "check": "wsjf_planner_excel_business_effect",
            "blocking_issues": ["business_effect_evidence_missing"],
            "evidence": None,
        }
    else:
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = evaluate(data, max_age_hours=args.max_age_hours)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
