#!/usr/bin/env python3
"""Build governed production runtime smoke evidence.

Consolida o resultado do validador público de runtime em um snapshot pequeno,
read-only e reversível. O script não executa deploy, merge, promoção de ambiente
nem alteração destrutiva; apenas classifica evidências já coletadas.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

STATE_SCORE = {
    "green": 100,
    "yellow": 70,
    "red": 20,
    "unknown": 40,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_parse_error": True, "path": str(path)}
    return payload if isinstance(payload, dict) else {"_parse_error": True, "path": str(path)}


def classify(validation: dict[str, Any] | None, readiness: dict[str, Any] | None) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if not validation:
        return "red", ["public_runtime_validation_missing"]
    if validation.get("_parse_error"):
        return "red", ["public_runtime_validation_invalid_json"]

    failed = int(validation.get("failed") or 0)
    success = float(validation.get("success_percentual") or 0)
    readiness_payload = readiness or validation.get("readiness") or {}
    readiness_percent = float(readiness_payload.get("readiness_percent") or 0)
    blocking = list(readiness_payload.get("blocking_issues") or [])
    operational_status = str(readiness_payload.get("operational_status") or "unknown").lower()

    if failed:
        blockers.append("required_endpoint_failed")
    if blocking:
        blockers.append("readiness_blocking_issues")
    if success < 100:
        blockers.append("runtime_smoke_below_100")
    if readiness_percent < 90:
        blockers.append("readiness_below_90")

    if blockers:
        if success >= 75 and readiness_percent >= 70:
            return "yellow", blockers
        return "red", blockers
    if operational_status in {"healthy", "ok", "green", "stable"} and success >= 100 and readiness_percent >= 90:
        return "green", []
    return "yellow", ["runtime_ready_but_status_not_healthy"]


def build_snapshot(
    validation: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    *,
    repository: str,
    branch: str,
    sha: str,
    run_id: str,
) -> dict[str, Any]:
    state, blockers = classify(validation, readiness)
    validation = validation or {}
    readiness_payload = readiness or validation.get("readiness") or {}
    success = float(validation.get("success_percentual") or 0)
    readiness_percent = float(readiness_payload.get("readiness_percent") or 0)
    score = round((success * 0.6) + (readiness_percent * 0.4)) if validation else STATE_SCORE[state]
    score = max(0, min(100, score))

    return {
        "schema_version": "1.0.0",
        "contract": "runtime-production-smoke-governed",
        "correlation_id": str(uuid4()),
        "generated_at": utc_now(),
        "repository": repository,
        "branch": branch,
        "sha": sha,
        "github_run_id": run_id,
        "state": state,
        "score": score,
        "production_ready": state == "green",
        "runtime": {
            "base_url": validation.get("base_url"),
            "environment": validation.get("environment", "prod"),
            "required_total": int(validation.get("total") or 0),
            "required_ok": int(validation.get("ok") or 0),
            "required_failed": int(validation.get("failed") or 0),
            "success_percentual": success,
        },
        "readiness": {
            "operational_status": readiness_payload.get("operational_status", "unknown"),
            "readiness_percent": readiness_percent,
            "blocking_issues": readiness_payload.get("blocking_issues") or [],
            "api_ready": readiness_payload.get("api_ready"),
            "runtime_ready": readiness_payload.get("runtime_ready"),
            "dashboard_ready": readiness_payload.get("dashboard_ready"),
        },
        "blockers": blockers,
        "guardrails": {
            "read_only": True,
            "deploy": False,
            "merge": False,
            "requires_human_for_prod_promotion": True,
            "rollback_action": "reverter PR do workflow/snapshot",
        },
        "next_action": "none" if state == "green" else "corrigir runtime público antes de declarar produção verde",
    }


def write_outputs(snapshot: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runtime-production-smoke-governed.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Runtime Production Smoke Governed",
        "",
        f"- State: `{snapshot['state']}`",
        f"- Score: `{snapshot['score']}%`",
        f"- Production ready: `{snapshot['production_ready']}`",
        f"- Repository: `{snapshot['repository']}`",
        f"- Branch: `{snapshot['branch']}`",
        f"- SHA: `{snapshot['sha']}`",
        f"- Correlation ID: `{snapshot['correlation_id']}`",
        "",
        "## Runtime",
        "",
        f"- Base URL: `{snapshot['runtime']['base_url']}`",
        f"- Required OK: `{snapshot['runtime']['required_ok']}/{snapshot['runtime']['required_total']}`",
        f"- Success: `{snapshot['runtime']['success_percentual']}%`",
        "",
        "## Readiness",
        "",
        f"- Operational status: `{snapshot['readiness']['operational_status']}`",
        f"- Readiness: `{snapshot['readiness']['readiness_percent']}%`",
        f"- Blockers: `{', '.join(snapshot['blockers']) or 'none'}`",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolida smoke runtime produção governado.")
    parser.add_argument("--validation", default="artifacts/runtime/public-runtime-validation.json")
    parser.add_argument("--readiness", default="artifacts/runtime/ops-readiness-report.json")
    parser.add_argument("--output-dir", default="artifacts/runtime-production-smoke-governed")
    parser.add_argument("--repository", default="")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--sha", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--enforce", action="store_true", help="Falha quando produção não estiver green.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validation = load_json(Path(args.validation))
    readiness = load_json(Path(args.readiness))
    snapshot = build_snapshot(
        validation,
        readiness,
        repository=args.repository,
        branch=args.branch,
        sha=args.sha,
        run_id=args.run_id,
    )
    write_outputs(snapshot, Path(args.output_dir))
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return 1 if args.enforce and snapshot["state"] != "green" else 0


if __name__ == "__main__":
    raise SystemExit(main())
