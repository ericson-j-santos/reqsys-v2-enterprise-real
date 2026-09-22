#!/usr/bin/env python3
"""Bloqueia crescimento descontrolado da superfície de GitHub Actions em PRs."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_DIR = ".github/workflows/"


@dataclass(frozen=True)
class SurfaceResult:
    status: str
    added: list[str]
    deleted: list[str]
    net_growth: int
    broad_pr_violations: list[str]
    canonical_pr_workflows: list[str]


def git_name_status(base_ref: str) -> list[tuple[str, str]]:
    completed = subprocess.run(
        ["git", "diff", "--name-status", "-M", f"origin/{base_ref}...HEAD", "--", ".github/workflows"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git diff falhou")
    entries: list[tuple[str, str]] = []
    for raw in completed.stdout.splitlines():
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        entries.append((status, path))
    return entries


def canonical_names(registry: dict[str, Any]) -> set[str]:
    path = registry.get("canonical_pr_path")
    if not isinstance(path, dict):
        raise ValueError("canonical_pr_path ausente no registry")
    names = {str(path.get("entry") or "").strip()}
    blocking = path.get("blocking")
    if not isinstance(blocking, list):
        raise ValueError("canonical_pr_path.blocking inválido")
    names.update(str(item).strip() for item in blocking)
    names.discard("")
    if not names:
        raise ValueError("caminho canônico vazio")
    return names


def workflow_name_and_broad_pr(path: Path) -> tuple[str, bool]:
    payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: workflow inválido")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError(f"{path}: workflow sem name")
    triggers = payload.get("on")
    if not isinstance(triggers, dict) or "pull_request" not in triggers:
        return name, False
    pr = triggers.get("pull_request")
    if pr in (None, ""):
        return name, True
    if isinstance(pr, dict):
        return name, not ("paths" in pr or "paths-ignore" in pr)
    return name, True


def evaluate(entries: list[tuple[str, str]], root: Path, registry: dict[str, Any]) -> SurfaceResult:
    added = sorted(path for status, path in entries if status.startswith("A") and path.startswith(WORKFLOW_DIR))
    deleted = sorted(path for status, path in entries if status.startswith("D") and path.startswith(WORKFLOW_DIR))
    net_growth = len(added) - len(deleted)
    allowed = canonical_names(registry)
    violations: list[str] = []

    for rel in added:
        target = root / rel
        if not target.is_file():
            violations.append(f"{rel}: arquivo adicionado não encontrado")
            continue
        try:
            name, broad = workflow_name_and_broad_pr(target)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            violations.append(f"{rel}: {exc}")
            continue
        if broad and name not in allowed:
            violations.append(f"{rel}: pull_request amplo fora do caminho canônico ({name})")

    status = "passed" if net_growth <= 0 and not violations else "blocked"
    return SurfaceResult(
        status=status,
        added=added,
        deleted=deleted,
        net_growth=net_growth,
        broad_pr_violations=violations,
        canonical_pr_workflows=sorted(allowed),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida orçamento da superfície de workflows.")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--registry", type=Path, default=Path("config/workflow-governance-registry.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/workflow-surface-budget.json"))
    args = parser.parse_args()

    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        result = evaluate(git_name_status(args.base_ref), Path.cwd(), registry)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
