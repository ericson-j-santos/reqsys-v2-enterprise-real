#!/usr/bin/env python3
"""Fail-fast budget for the pull-request CI critical path."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "ci-workflow-pareto-policy.json"

SPECIALIZED = {
    "ReqSys 360 Coherence Gate": {
        "workflow": ".github/workflows/reqsys-360-coherence-gate.yml",
        "forbidden_pr_paths": {
            "frontend/**",
            "backend/**",
            "backend-dotnet/**",
            "runtime/**",
            "services/**",
        },
        "required_pr_paths": {
            "frontend/src/router/**",
            "frontend/tests/e2e/reqsys-360-navigation.spec.js",
            "scripts/reqsys_360_*.py",
            "tests/test_reqsys_360_*.py",
            ".github/workflows/reqsys-360-coherence-gate.yml",
        },
        "post_merge_required_paths": {"backend/**", "frontend/**"},
    },
    "Trilha D — Qualidade e Governança": {
        "workflow": ".github/workflows/trilha-d-qualidade-governanca.yml",
        "forbidden_pr_paths": {"backend/**"},
        "required_pr_paths": {
            "scripts/trilha_d_qualidade_governanca.py",
            "tests/test_trilha_d_qualidade_governanca.py",
            ".github/workflows/trilha-d-qualidade-governanca.yml",
        },
        "post_merge_required_paths": {"backend/**"},
    },
    "Kindle Knowledge Local Cache": {
        "workflow": ".github/workflows/kindle-knowledge-local-cache.yml",
        "forbidden_pr_paths": {".github/self-hosted-runner-policy.json"},
        "required_pr_paths": {
            "scripts/kindle_knowledge_local_cache.py",
            "tests/test_kindle_knowledge_local_cache.py",
            ".github/workflows/kindle-knowledge-local-cache.yml",
        },
        "post_merge_required_paths": {".github/self-hosted-runner-policy.json"},
    },
}

KINDLE_PHYSICAL_JOBS = ("noteri", "desktop_recover", "desktop")


def _event_block(text: str, event: str) -> str:
    lines = text.splitlines()
    marker = f"  {event}:"
    try:
        start = next(i for i, line in enumerate(lines) if line == marker)
    except StopIteration:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if re.match(r"^  [A-Za-z0-9_-]+:", line):
            end = i
            break
    return "\n".join(lines[start:end])


def _job_block(text: str, job: str) -> str:
    lines = text.splitlines()
    marker = f"  {job}:"
    try:
        start = next(i for i, line in enumerate(lines) if line == marker)
    except StopIteration:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if re.match(r"^  [A-Za-z0-9_-]+:", line):
            end = i
            break
    return "\n".join(lines[start:end])


def _paths(block: str) -> set[str]:
    found: set[str] = set()
    for raw in block.splitlines():
        match = re.match(r"^\s*-\s*['\"]([^'\"]+)['\"]\s*$", raw)
        if match:
            found.add(match.group(1))
    return found


def _policy_blockers(policy: dict) -> list[str]:
    blockers: list[str] = []
    protected = list(policy.get("protected_workflows") or [])
    report_only = set(policy.get("report_only_workflows") or [])
    budget = int(
        policy.get(
            "blocking_workflow_budget",
            policy.get("target_average_workflows_per_pr", 10),
        )
    )
    if len(protected) != len(set(protected)):
        blockers.append("protected_workflows contém duplicatas")
    overlap = sorted(set(protected) & report_only)
    if overlap:
        blockers.append(f"workflows protegidos também marcados report-only: {overlap}")
    if len(protected) > budget:
        blockers.append(
            f"blocking workflow budget excedido: {len(protected)} > {budget}"
        )
    return blockers


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def specialized_candidates(changed_files: Iterable[str]) -> list[str]:
    files = [item.strip() for item in changed_files if item.strip()]
    selected: list[str] = []
    for name, contract in SPECIALIZED.items():
        if any(_matches_any(path, contract["required_pr_paths"]) for path in files):
            selected.append(name)
    return sorted(selected)


def evaluate_repository(root: Path = ROOT, changed_files: Iterable[str] = ()) -> dict:
    policy_path = root / "config" / "ci-workflow-pareto-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    blockers = _policy_blockers(policy)
    routing: dict[str, dict] = {}

    for name, contract in SPECIALIZED.items():
        workflow_path = root / contract["workflow"]
        if not workflow_path.exists():
            blockers.append(f"workflow ausente: {contract['workflow']}")
            continue
        text = workflow_path.read_text(encoding="utf-8")
        pr_paths = _paths(_event_block(text, "pull_request"))
        push_paths = _paths(_event_block(text, "push"))

        broad = sorted(pr_paths & set(contract["forbidden_pr_paths"]))
        missing = sorted(set(contract["required_pr_paths"]) - pr_paths)
        post_merge_missing = sorted(
            set(contract["post_merge_required_paths"]) - push_paths
        )
        if broad:
            blockers.append(f"{name}: PR ainda contém rotas amplas: {broad}")
        if missing:
            blockers.append(f"{name}: rotas PR mínimas ausentes: {missing}")
        if post_merge_missing:
            blockers.append(
                f"{name}: rede de segurança pós-merge ausente: {post_merge_missing}"
            )

        routing[name] = {
            "pr_paths": sorted(pr_paths),
            "forbidden_present": broad,
            "required_missing": missing,
            "post_merge_missing": post_merge_missing,
        }

    kindle_text = (
        root / SPECIALIZED["Kindle Knowledge Local Cache"]["workflow"]
    ).read_text(encoding="utf-8")
    for job in KINDLE_PHYSICAL_JOBS:
        block = _job_block(kindle_text, job)
        if not block:
            blockers.append(f"Kindle: job físico ausente: {job}")
        elif "github.event_name != 'pull_request'" not in block:
            blockers.append(f"Kindle: job físico {job} ainda pode executar em PR")

    protected = list(policy.get("protected_workflows") or [])
    budget = int(
        policy.get(
            "blocking_workflow_budget",
            policy.get("target_average_workflows_per_pr", 10),
        )
    )
    changed = [item.strip() for item in changed_files if item.strip()]
    candidates = specialized_candidates(changed)
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-ci-budget-guard",
        "status": "passed" if not blockers else "blocked",
        "blocking_workflow_budget": budget,
        "blocking_workflow_count": len(protected),
        "blocking_workflows": protected,
        "protected_workflows_preserved": not bool(
            set(protected) & set(policy.get("report_only_workflows") or [])
        ),
        "specialized_candidates_for_diff": candidates,
        "changed_file_count": len(changed),
        "routing": routing,
        "blockers": blockers,
        "production_touched": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed_files: list[str] = []
    if args.changed_files and args.changed_files.exists():
        changed_files = args.changed_files.read_text(encoding="utf-8").splitlines()

    result = evaluate_repository(ROOT, changed_files)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
