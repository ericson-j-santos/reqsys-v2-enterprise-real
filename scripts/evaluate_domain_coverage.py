#!/usr/bin/env python3
"""Avalia cobertura do backend por domínio arquitetural."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_COVERAGE = "artifacts/domain-coverage/coverage.json"
DEFAULT_POLICY = "config/domain-coverage-policy.json"
DEFAULT_OUTPUT = "artifacts/domain-coverage/report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").lstrip("./")
    return normalized.removeprefix("backend/")


def file_coverage(item: dict[str, Any]) -> tuple[int, int]:
    summary = item.get("summary") or {}
    return int(summary.get("covered_lines", 0)), int(summary.get("num_statements", 0))


def evaluate(coverage: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    files = coverage.get("files") or {}
    normalized = {normalize_path(path): data for path, data in files.items()}
    tolerance = float(policy.get("allowed_regression_percentage_points", 0.0))
    baseline = policy.get("baseline") or {}
    domains: dict[str, Any] = {}
    regressions: list[str] = []
    invalid_domains: list[str] = []

    for name, rule in (policy.get("domains") or {}).items():
        prefixes = [normalize_path(path) for path in rule.get("paths", [])]
        covered = 0
        statements = 0
        matched_files: list[str] = []

        for path, data in normalized.items():
            if any(path.startswith(prefix) for prefix in prefixes):
                current_covered, current_statements = file_coverage(data)
                covered += current_covered
                statements += current_statements
                matched_files.append(path)

        if not matched_files or statements <= 0:
            invalid_domains.append(name)

        percent = round((covered / statements * 100), 2) if statements else 0.0
        baseline_percent = baseline.get(name)
        target = float(rule.get("target_percent", 0.0))
        regression = baseline_percent is not None and percent + tolerance < float(baseline_percent)
        if regression:
            regressions.append(name)

        domains[name] = {
            "coverage_percent": percent,
            "baseline_percent": baseline_percent,
            "target_percent": target,
            "target_met": percent >= target,
            "regression": regression,
            "covered_lines": covered,
            "statements": statements,
            "matched_files": sorted(matched_files),
        }

    if invalid_domains:
        status = "invalid_measurement"
    elif regressions:
        status = "failed"
    elif not baseline:
        status = "baseline_required"
    else:
        status = "passed"

    return {
        "schema_version": "1.1.0",
        "mode": policy.get("mode", "record_then_regression"),
        "status": status,
        "allowed_regression_percentage_points": tolerance,
        "regressions": regressions,
        "invalid_domains": invalid_domains,
        "domains": domains,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate coverage by backend domain")
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate(load_json(Path(args.coverage)), load_json(Path(args.policy)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else f"domain_coverage_status={report['status']} output={output}")
    return 1 if report["status"] in {"failed", "invalid_measurement"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
