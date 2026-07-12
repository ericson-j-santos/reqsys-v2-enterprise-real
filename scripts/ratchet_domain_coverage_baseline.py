#!/usr/bin/env python3
"""Eleva baselines de cobertura somente quando houver melhoria real e suficiente."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ratchet(
    report: dict[str, Any],
    policy: dict[str, Any],
    minimum_gain: float = 0.5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if report.get("status") not in {"passed", "baseline_required"}:
        raise ValueError(f"Medição não elegível: {report.get('status')}")

    current_baseline = policy.get("baseline") or {}
    if not current_baseline:
        raise ValueError("Ratchet exige baseline inicial já ativado")

    domains = report.get("domains") or {}
    configured = policy.get("domains") or {}
    if set(domains) != set(configured):
        raise ValueError("Domínios medidos diferem da política")

    next_baseline = dict(current_baseline)
    promoted: dict[str, Any] = {}
    unchanged: dict[str, Any] = {}

    for name, item in domains.items():
        if not item.get("matched_files") or int(item.get("statements", 0)) <= 0:
            raise ValueError(f"Domínio sem evidência válida: {name}")

        measured = float(item["coverage_percent"])
        previous = float(current_baseline[name])
        gain = round(measured - previous, 2)

        if gain >= minimum_gain:
            next_baseline[name] = measured
            promoted[name] = {
                "previous_percent": previous,
                "measured_percent": measured,
                "gain_percentage_points": gain,
            }
        else:
            unchanged[name] = {
                "baseline_percent": previous,
                "measured_percent": measured,
                "delta_percentage_points": gain,
                "reason": "gain_below_threshold" if gain >= 0 else "regression_not_promoted",
            }

    updated = dict(policy)
    updated["schema_version"] = "1.2.0"
    updated["mode"] = "regression_gate"
    updated["baseline"] = next_baseline

    evidence = {
        "schema_version": "1.0.0",
        "status": "proposal_ready" if promoted else "no_change",
        "requires_human_approval": True,
        "minimum_gain_percentage_points": minimum_gain,
        "promoted": promoted,
        "unchanged": unchanged,
    }
    return updated, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--policy", default="config/domain-coverage-policy.json")
    parser.add_argument("--minimum-gain", type=float, default=0.5)
    parser.add_argument("--output-policy", default="artifacts/domain-coverage/ratcheted-policy.json")
    parser.add_argument("--output-evidence", default="artifacts/domain-coverage/ratchet-evidence.json")
    args = parser.parse_args()

    updated, evidence = ratchet(load(Path(args.report)), load(Path(args.policy)), args.minimum_gain)
    output_policy = Path(args.output_policy)
    output_evidence = Path(args.output_evidence)
    output_policy.parent.mkdir(parents=True, exist_ok=True)
    output_evidence.parent.mkdir(parents=True, exist_ok=True)
    output_policy.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
