#!/usr/bin/env python3
"""Gera proposta versionada de baseline a partir de uma medição válida."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_proposal(report: dict[str, Any], policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if report.get("status") not in {"baseline_required", "passed"}:
        raise ValueError(f"Medição não elegível: {report.get('status')}")

    domains = report.get("domains") or {}
    configured = policy.get("domains") or {}
    if set(domains) != set(configured):
        raise ValueError("Domínios medidos diferem da política versionada")

    baseline: dict[str, float] = {}
    changes: dict[str, Any] = {}
    previous = policy.get("baseline") or {}

    for name, item in domains.items():
        if not item.get("matched_files") or int(item.get("statements", 0)) <= 0:
            raise ValueError(f"Domínio sem evidência válida: {name}")
        current = float(item["coverage_percent"])
        baseline[name] = current
        old = previous.get(name)
        changes[name] = {
            "previous_percent": old,
            "current_percent": current,
            "delta_percentage_points": None if old is None else round(current - float(old), 2),
            "target_percent": float(item.get("target_percent", 0.0)),
            "regression": old is not None and current < float(old),
            "improvement": old is not None and current > float(old),
        }

    updated = dict(policy)
    updated["schema_version"] = "1.1.0"
    updated["mode"] = "regression_gate"
    updated["baseline"] = baseline

    diff = {
        "schema_version": "1.0.0",
        "status": "proposal_ready",
        "requires_human_approval": True,
        "baseline_mode_before": policy.get("mode"),
        "baseline_mode_after": "regression_gate",
        "domains": changes,
    }
    return updated, diff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--policy", default="config/domain-coverage-policy.json")
    parser.add_argument("--output-policy", default="artifacts/domain-coverage/proposed-policy.json")
    parser.add_argument("--output-diff", default="artifacts/domain-coverage/baseline-diff.json")
    args = parser.parse_args()

    updated, diff = build_proposal(load(Path(args.report)), load(Path(args.policy)))
    output_policy = Path(args.output_policy)
    output_diff = Path(args.output_diff)
    output_policy.parent.mkdir(parents=True, exist_ok=True)
    output_diff.parent.mkdir(parents=True, exist_ok=True)
    output_policy.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_diff.write_text(json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(diff, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
