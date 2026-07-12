#!/usr/bin/env python3
"""Smoke público e verificação de sincronização da tendência comparativa do Advisor."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_comparative_public_smoke_trend"
REQUIRED_ENVIRONMENTS = ("DEV", "STG", "PROD")
MAX_SAMPLES = 90


def _load_json(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=20) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _load_text(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=20) as response:  # nosec B310
            return response.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def validate_sync(index_html: str, runtime: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    runtime_card = runtime.get("cards", {}).get(CARD_KEY, {})
    brief_card = brief.get("cards", {}).get(CARD_KEY, brief.get(CARD_KEY, {}))
    issues: list[str] = []

    if CARD_KEY not in index_html:
        issues.append("card-hook-missing")
    if not runtime_card:
        issues.append("runtime-card-missing")
    if not brief_card:
        issues.append("brief-card-missing")

    for name, card in (("runtime", runtime_card), ("brief", brief_card)):
        if card:
            if card.get("mode") != "report-only":
                issues.append(f"{name}-mode-unsafe")
            if card.get("production_blocker") is not False:
                issues.append(f"{name}-production-blocker-unsafe")
            if card.get("human_approval_required") is not True:
                issues.append(f"{name}-human-approval-missing")

    synchronized = bool(runtime_card and brief_card and _fingerprint(runtime_card) == _fingerprint(brief_card))
    if runtime_card and brief_card and not synchronized:
        issues.append("state-brief-drift")

    return {
        "schema_version": "1.0",
        "status": "PUBLIC_TREND_SMOKE_PASSED" if not issues else "PUBLIC_TREND_SMOKE_REVIEW",
        "synchronized": synchronized,
        "issues": sorted(set(issues)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "runtime_fingerprint": _fingerprint(runtime_card) if runtime_card else None,
        "brief_fingerprint": _fingerprint(brief_card) if brief_card else None,
    }


def append_history(history: dict[str, Any], environment: str, result: dict[str, Any]) -> dict[str, Any]:
    environment = environment.upper()
    if environment not in REQUIRED_ENVIRONMENTS:
        raise ValueError(f"Ambiente não governado: {environment}")

    output = json.loads(json.dumps(history or {}))
    output.setdefault("schema_version", "1.0")
    output.setdefault("mode", "report-only")
    output.setdefault("production_blocker", False)
    output.setdefault("human_approval_required", True)
    environments = output.setdefault("environments", {})
    bucket = environments.setdefault(environment, {"samples": []})

    sample = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "synchronized": result["synchronized"],
        "issues": result["issues"],
        "fingerprint": _fingerprint({k: result.get(k) for k in ("status", "synchronized", "issues")}),
    }
    samples = bucket.setdefault("samples", [])
    if not samples or samples[-1].get("fingerprint") != sample["fingerprint"]:
        samples.append(sample)
    bucket["samples"] = samples[-MAX_SAMPLES:]

    total = len(bucket["samples"])
    passed = sum(1 for item in bucket["samples"] if item.get("status") == "PUBLIC_TREND_SMOKE_PASSED")
    synced = sum(1 for item in bucket["samples"] if item.get("synchronized") is True)
    streak = 0
    for item in reversed(bucket["samples"]):
        if item.get("status") == "PUBLIC_TREND_SMOKE_PASSED" and item.get("synchronized") is True:
            streak += 1
        else:
            break
    bucket["summary"] = {
        "samples": total,
        "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        "sync_rate": round((synced / total) * 100, 2) if total else 0.0,
        "stable_sequence": streak,
    }

    covered = [env for env in REQUIRED_ENVIRONMENTS if environments.get(env, {}).get("summary", {}).get("samples", 0) > 0]
    output["summary"] = {
        "environment_coverage": len(covered),
        "covered_environments": covered,
        "total_environments": len(REQUIRED_ENVIRONMENTS),
        "eligible_for_human_review": len(covered) == 3 and all(
            environments[env]["summary"]["pass_rate"] >= 98
            and environments[env]["summary"]["sync_rate"] >= 98
            and environments[env]["summary"]["stable_sequence"] >= 20
            for env in REQUIRED_ENVIRONMENTS
        ),
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--history")
    parser.add_argument("--output", required=True)
    parser.add_argument("--history-output", required=True)
    args = parser.parse_args()

    result = validate_sync(_load_text(args.index), _load_json(args.runtime), _load_json(args.brief))
    history = _load_json(args.history) if args.history and Path(args.history).exists() else {}
    history = append_history(history, args.environment, result)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.history_output).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
