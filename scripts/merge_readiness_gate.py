#!/usr/bin/env python3
"""Merge Readiness Gate.

Valida condições objetivas que costumam gerar retrabalho operacional:
- branch atrasada em relação à base;
- conflito de merge;
- PR grande demais;
- excesso de alterações em workflows;
- mistura de domínios de mudança no mesmo PR.

A saída JSON pode alimentar dashboards, artifacts e análises históricas.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class GateConfig:
    base_ref: str
    max_changed_files: int
    max_workflow_files: int
    max_domains: int
    output: Path


@dataclass(frozen=True)
class GateResult:
    status: str
    base_ref: str
    ahead_by: int
    behind_by: int
    changed_files: int
    workflow_files: int
    domains: list[str]
    blocking_issues: list[str]
    warnings: list[str]


def run_git(args: Iterable[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} falhou com código {completed.returncode}: {completed.stderr.strip()}"
        )
    return completed


def git_stdout(args: Iterable[str]) -> str:
    return run_git(args).stdout.strip()


def count_rev_range(rev_range: str) -> int:
    value = git_stdout(["rev-list", "--count", rev_range])
    return int(value or "0")


def changed_files(base_ref: str) -> list[str]:
    output = git_stdout(["diff", "--name-only", f"origin/{base_ref}...HEAD"])
    return [line for line in output.splitlines() if line.strip()]


def classify_domain(path: str) -> str:
    if path.startswith(".github/workflows/"):
        return "ci-workflows"
    if path.startswith("backend/"):
        return "backend"
    if path.startswith("frontend/"):
        return "frontend"
    if path.startswith("infra/") or path.endswith("fly.toml"):
        return "infra"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("scripts/"):
        return "automation-scripts"
    if path.startswith("tests/"):
        return "tests"
    return "other"


def has_merge_conflict(base_ref: str) -> bool:
    run_git(["checkout", "-B", "__merge_readiness_probe", "HEAD"])
    merge = run_git(["merge", "--no-commit", "--no-ff", f"origin/{base_ref}"], check=False)
    conflict = merge.returncode != 0
    run_git(["merge", "--abort"], check=False)
    run_git(["checkout", "-"], check=False)
    return conflict


def evaluate(config: GateConfig) -> GateResult:
    run_git(["fetch", "origin", config.base_ref, "--prune"])

    ahead_by = count_rev_range(f"origin/{config.base_ref}..HEAD")
    behind_by = count_rev_range(f"HEAD..origin/{config.base_ref}")
    files = changed_files(config.base_ref)
    workflow_files = [path for path in files if path.startswith(".github/workflows/")]
    domains = sorted({classify_domain(path) for path in files})

    blocking: list[str] = []
    warnings: list[str] = []

    if behind_by > 0:
        blocking.append(
            f"Branch está {behind_by} commit(s) atrás de {config.base_ref}; rebase/update obrigatório antes do merge."
        )

    if has_merge_conflict(config.base_ref):
        blocking.append("Merge dry-run detectou conflito com a branch base.")

    if len(files) > config.max_changed_files:
        blocking.append(
            f"PR grande demais: {len(files)} arquivos alterados; limite operacional é {config.max_changed_files}."
        )

    if len(workflow_files) > config.max_workflow_files:
        blocking.append(
            f"Excesso de workflows alterados: {len(workflow_files)}; limite operacional é {config.max_workflow_files}."
        )

    if len(domains) > config.max_domains:
        warnings.append(
            f"PR mistura {len(domains)} domínios ({', '.join(domains)}); considerar fatiamento por incremento."
        )

    status = "blocked" if blocking else "ready"
    return GateResult(
        status=status,
        base_ref=config.base_ref,
        ahead_by=ahead_by,
        behind_by=behind_by,
        changed_files=len(files),
        workflow_files=len(workflow_files),
        domains=domains,
        blocking_issues=blocking,
        warnings=warnings,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida prontidão objetiva de merge.")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--max-changed-files", type=int, default=25)
    parser.add_argument("--max-workflow-files", type=int, default=3)
    parser.add_argument("--max-domains", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("artifacts/merge-readiness/merge-readiness.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = GateConfig(
        base_ref=args.base_ref,
        max_changed_files=args.max_changed_files,
        max_workflow_files=args.max_workflow_files,
        max_domains=args.max_domains,
        output=args.output,
    )

    result = evaluate(config)
    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.output.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if result.status == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - defensive CI failure clarity
        print(f"merge-readiness gate falhou: {exc}", file=sys.stderr)
        raise SystemExit(2)
