#!/usr/bin/env python3
"""Build DEV→STG→PROD executive promotion readiness evidence.

Offline/report-only by default. It consolidates Executive Readiness with
homologation evidence from all created environments.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")
DEFAULT_INPUTS = {
    "executive_readiness": Path("artifacts/executive-readiness-gate/executive-readiness-gate.json"),
    "runtime_index": Path("docs/ops-dashboard/data/runtime-executive-index.json"),
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize(value: Any, default: str = "unknown") -> str:
    return str(value if value is not None else default).strip().lower() or default


def evidence_candidates(env: str) -> list[Path]:
    return [
        Path(f"artifacts/fly-homologation/evidence-{env}.json"),
        Path(f"audit/fly-homologation/evidence-{env}.json"),
        Path(f"docs/ops-dashboard/data/fly-homologation-evidence-{env}.json"),
    ]


def first_json(paths: list[Path]) -> tuple[dict[str, Any], str | None]:
    for path in paths:
        payload = load_json(path)
        if payload:
            return payload, str(path)
    return {}, None


def env_summary(env: str) -> dict[str, Any]:
    evidence, source = first_json(evidence_candidates(env))
    probes = evidence.get("probes") or []
    blocking = evidence.get("blocking_issues") or []
    ok = bool(evidence.get("ok")) if evidence else False
    return {
        "environment": env,
        "available": bool(evidence),
        "ok": ok,
        "state": "green" if ok else "red" if evidence else "unknown",
        "source": source,
        "base_url": evidence.get("base_url", ""),
        "expected_sha": evidence.get("expected_sha", ""),
        "observed_sha": evidence.get("observed_sha", ""),
        "probe_count": len(probes),
        "blocking_issue_count": len(blocking),
        "blocking_issues": blocking,
        "generated_at_epoch": evidence.get("generated_at_epoch"),
    }


def executive_summary(gate: dict[str, Any], runtime_index: dict[str, Any]) -> dict[str, Any]:
    readiness = gate.get("executive_readiness") or {}
    runtime_summary = runtime_index.get("summary") or {}
    decision = readiness.get("decision") or runtime_summary.get("executive_readiness_decision") or "UNKNOWN"
    ready = bool(readiness.get("ready_for_production") or runtime_summary.get("production_ready"))
    blockers = readiness.get("blockers") or []
    return {
        "available": bool(gate or runtime_index),
        "ready_for_production": ready,
        "decision": str(decision).upper(),
        "score": int(readiness.get("score") or runtime_summary.get("executive_score") or 0),
        "risk": readiness.get("risk") or runtime_summary.get("risk") or "unknown",
        "blockers": blockers,
        "blocker_count": len(blockers),
    }


def build(repo: str, expected_sha: str = "") -> dict[str, Any]:
    gate = load_json(DEFAULT_INPUTS["executive_readiness"])
    runtime_index = load_json(DEFAULT_INPUTS["runtime_index"])
    executive = executive_summary(gate, runtime_index)
    environments = [env_summary(env) for env in ENVIRONMENTS]

    missing = [item["environment"] for item in environments if not item["available"]]
    failed = [item["environment"] for item in environments if item["available"] and not item["ok"]]
    ready_envs = [item["environment"] for item in environments if item["ok"]]
    production_blockers: list[str] = []

    if not executive["ready_for_production"]:
        production_blockers.append("executive_readiness_not_ready")
    production_blockers.extend(f"env_{env}_evidence_missing" for env in missing)
    production_blockers.extend(f"env_{env}_failed" for env in failed)

    if expected_sha:
        for item in environments:
            observed = str(item.get("observed_sha") or "")
            expected = str(item.get("expected_sha") or expected_sha)
            if item["available"] and expected and observed and observed[:12] != expected[:12]:
                production_blockers.append(f"env_{item['environment']}_sha_mismatch")

    ready = not production_blockers
    return {
        "schema_version": "1.0.0",
        "kind": "environment_promotion_readiness",
        "repo": repo,
        "generated_at_epoch": int(time.time()),
        "mode": "report_only",
        "expected_sha": expected_sha,
        "decision": "READY_FOR_PROD_PROMOTION" if ready else "BLOCKED_FOR_PROD_PROMOTION",
        "ready_for_prod_promotion": ready,
        "production_blockers": sorted(set(production_blockers)),
        "executive_readiness": executive,
        "environments": environments,
        "coverage": {
            "required_environments": list(ENVIRONMENTS),
            "ready_environments": ready_envs,
            "missing_environments": missing,
            "failed_environments": failed,
            "coverage_percent": round((len(ready_envs) / len(ENVIRONMENTS)) * 100, 2),
        },
        "guardrails": [
            "dev_stg_prod_required_before_prod_promotion",
            "executive_readiness_required",
            "report_only_by_default",
            "no_secret_capture",
            "no_runtime_api_call_from_public_dashboard",
        ],
        "next_safe_increment": "wire_environment_promotion_readiness_to_ops_dashboard_top_indicator",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build environment promotion readiness evidence")
    parser.add_argument("--repo", default="local/reqsys")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--output", type=Path, default=Path("artifacts/environment-promotion-readiness/environment-promotion-readiness.json"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = build(args.repo, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "ready": payload["ready_for_prod_promotion"], "blockers": payload["production_blockers"]}, ensure_ascii=False))
    return 1 if args.strict and not payload["ready_for_prod_promotion"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
