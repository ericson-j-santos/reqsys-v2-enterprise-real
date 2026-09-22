#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = Path(os.getenv("MOVIMENTO_EMAIL_EVIDENCE_ROOT", "/var/lib/reqsys-24x7/movimento-email/evidence"))
INTERVAL = max(60, int(os.getenv("MOVIMENTO_EMAIL_SYNC_INTERVAL_SECONDS", "900")))
LAG_DAYS = max(0, int(os.getenv("MOVIMENTO_EMAIL_DATA_LAG_DAYS", "0")))
TIMEZONE = ZoneInfo(os.getenv("MOVIMENTO_EMAIL_TIMEZONE", "America/Sao_Paulo"))
MAPPING = os.getenv("MOVIMENTO_EMAIL_SOURCE_MAP", "").strip()


def run_once() -> int:
    ref = (datetime.now(TIMEZONE).date() - timedelta(days=LAG_DAYS)).isoformat()
    correlation_id = f"pc24x7-movimento-{uuid.uuid4()}"
    cycle = EVIDENCE_ROOT / correlation_id
    cycle.mkdir(parents=True, exist_ok=True)

    base = [
        sys.executable,
        str(ROOT / "scripts" / "sincronizar_movimento_email_corporate.py"),
        "--data-referencia", ref,
        "--correlation-id", correlation_id,
        "--source-sha", os.getenv("REQSYS_SOURCE_SHA", ""),
    ]
    if MAPPING:
        base += ["--mapping", MAPPING]

    phases = [
        ("dry-run", cycle / "01-dry-run.json"),
        ("apply", cycle / "02-apply.json"),
        ("apply", cycle / "03-repeat.json"),
    ]

    summary = {
        "captured_at": datetime.now(TIMEZONE).isoformat(),
        "correlation_id": correlation_id,
        "data_referencia": ref,
        "runtime": "pc24x7",
        "synthetic": False,
        "phases": [],
        "passed": False,
    }

    for mode, evidence in phases:
        cmd = base + ["--mode", mode, "--evidence", str(evidence)]
        completed = subprocess.run(cmd, cwd=ROOT, check=False)
        payload = json.loads(evidence.read_text(encoding="utf-8")) if evidence.exists() else {}
        summary["phases"].append({
            "mode": mode,
            "exit_code": completed.returncode,
            "status": payload.get("status"),
            "repeat_action": payload.get("repeat_action"),
            "business_data_observed": payload.get("business_data_observed"),
        })
        if completed.returncode != 0:
            break

    if len(summary["phases"]) == 3:
        repeat = json.loads((cycle / "03-repeat.json").read_text(encoding="utf-8"))
        summary["passed"] = repeat.get("status") == "noop" and repeat.get("repeat_action") == "already_present_no_write"

    (cycle / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = EVIDENCE_ROOT / "latest.json"
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["passed"] else 2


def main() -> int:
    once = os.getenv("MOVIMENTO_EMAIL_RUN_ONCE", "").strip().lower() in {"1", "true", "yes"}
    while True:
        run_once()
        if once:
            return 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
