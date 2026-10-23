#!/usr/bin/env python3
"""Avalia o relatório do Mutmut contra um baseline que só pode melhorar."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

KNOWN_STATUSES = {
    "killed",
    "no tests",
    "skipped",
    "suspicious",
    "survived",
    "timeout",
}


def parse_results(path: Path) -> tuple[Counter[str], list[str]]:
    counts: Counter[str] = Counter()
    malformed: list[str] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if ": " not in line:
            malformed.append(f"line {line_number}: missing status separator")
            continue
        _, status = line.rsplit(": ", 1)
        if status not in KNOWN_STATUSES:
            malformed.append(f"line {line_number}: unknown status {status!r}")
            continue
        counts[status] += 1

    return counts, malformed


def evaluate_results(results_path: Path, policy_path: Path) -> dict[str, Any]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    limits = policy.get("max_counts")
    if not isinstance(limits, dict) or not limits:
        raise ValueError("policy.max_counts must be a non-empty object")

    counts, malformed = parse_results(results_path)
    violations = list(malformed)

    for status, raw_limit in limits.items():
        if status not in KNOWN_STATUSES:
            raise ValueError(f"policy contains unknown status: {status!r}")
        if not isinstance(raw_limit, int) or isinstance(raw_limit, bool) or raw_limit < 0:
            raise ValueError(f"policy limit for {status!r} must be a non-negative integer")
        observed = counts[status]
        if observed > raw_limit:
            violations.append(f"{status}: observed={observed} limit={raw_limit}")

    return {
        "schema_version": "1.0",
        "status": "passed" if not violations else "failed",
        "results_file": str(results_path),
        "policy_file": str(policy_path),
        "baseline": policy.get("baseline", {}),
        "scope": policy.get("scope"),
        "counts_semantics": "statuses emitted by `mutmut results`; killed mutants are omitted",
        "counts": {status: counts[status] for status in sorted(KNOWN_STATUSES)},
        "limits": limits,
        "violations": violations,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = evaluate_results(args.results, args.policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
