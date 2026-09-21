#!/usr/bin/env python3
"""Bloqueia criadores diretos de PR para main em GitHub Actions.

Toda automação que publique uma PR em main deve passar pelo autoabridor
governado, que exige Pre-PR Readiness verde no HEAD exato antes do POST /pulls.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

WORKFLOW_GLOBS = ("*.yml", "*.yaml")
DIRECT_CREATE_PATTERNS = (
    re.compile(r"gh\s+pr\s+create\b", re.IGNORECASE),
    re.compile(r"gh\s+api[^\n]*--method\s+POST[^\n]*[/\"]pulls\b", re.IGNORECASE),
    re.compile(r"github\.rest\.pulls\.create\s*\(", re.IGNORECASE),
)
LITERAL_MAIN_PATTERNS = (
    re.compile(r"--base\s+[\"']?main[\"']?(?:\s|\\|$)", re.IGNORECASE),
    re.compile(r"[\"']base[\"']\s*:\s*[\"']main[\"']", re.IGNORECASE),
    re.compile(r"base\s*:\s*main(?:\s|$)", re.IGNORECASE),
)
GOVERNED_OPENER = "scripts/auto_open_agent_pr.py"


def workflow_files(root: Path) -> list[Path]:
    directory = root / ".github" / "workflows"
    files: set[Path] = set()
    for pattern in WORKFLOW_GLOBS:
        files.update(directory.glob(pattern))
    return sorted(files)


def run_blocks(text: str) -> Iterable[str]:
    """Retorna blocos shell aproximados sem depender do parser YAML."""
    lines = text.splitlines()
    current: list[str] = []
    in_run = False
    run_indent = -1
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"^\s*run:\s*\|[-+]?\s*$", line):
            if current:
                yield "\n".join(current)
            current = []
            in_run = True
            run_indent = indent
            continue
        if in_run:
            if line.strip() and indent <= run_indent:
                if current:
                    yield "\n".join(current)
                current = []
                in_run = False
                run_indent = -1
            else:
                current.append(line)
    if current:
        yield "\n".join(current)


def direct_main_creation_blocks(text: str) -> list[str]:
    violations: list[str] = []
    for block in run_blocks(text):
        if not any(pattern.search(block) for pattern in DIRECT_CREATE_PATTERNS):
            continue
        if any(pattern.search(block) for pattern in LITERAL_MAIN_PATTERNS):
            violations.append(block)
    return violations


def validate(root: Path) -> dict[str, object]:
    violations: list[dict[str, object]] = []
    observed_creators: list[str] = []
    for path in workflow_files(root):
        text = path.read_text(encoding="utf-8")
        blocks = direct_main_creation_blocks(text)
        if any(pattern.search(text) for pattern in DIRECT_CREATE_PATTERNS):
            observed_creators.append(path.relative_to(root).as_posix())
        if not blocks:
            continue
        if GOVERNED_OPENER in text:
            # A existência do opener no mesmo workflow não autoriza um segundo
            # POST direto; cada bloco literal para main continua proibido.
            pass
        violations.append(
            {
                "path": path.relative_to(root).as_posix(),
                "direct_main_blocks": len(blocks),
                "reason": "direct_main_pr_creation_bypasses_ready_for_pr",
            }
        )
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-pr-creation-readiness-enforcement",
        "valid": not violations,
        "governed_opener": GOVERNED_OPENER,
        "observed_pr_creator_workflows": observed_creators,
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("artifacts/pr-creation-path-guard/report.json"))
    args = parser.parse_args()
    report = validate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
