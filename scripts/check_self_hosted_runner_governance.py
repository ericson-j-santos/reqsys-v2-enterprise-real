#!/usr/bin/env python3
"""Bloqueia uso não governado de self-hosted runners em workflows GitHub Actions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

SELF_HOSTED_PATTERN = re.compile(r"(^|[\s\[,:'\"])(self-hosted)([\s\],:'\"]|$)", re.IGNORECASE)
RUNS_ON_PATTERN = re.compile(r"^(?P<indent>\s*)runs-on\s*:\s*(?P<value>.*?)(?:\s+#.*)?$")


def workflow_files(root: Path) -> Iterable[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.exists():
        return []
    return sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])


def _contains_self_hosted(value: str) -> bool:
    return bool(SELF_HOSTED_PATTERN.search(value))


def find_self_hosted_usages(root: Path) -> list[str]:
    """Encontra apenas labels literais `self-hosted` associadas a `runs-on`.

    Textos em nomes de workflow, paths, comandos, comentários ou artifacts não são
    considerados uso de runner. Também cobre listas YAML em múltiplas linhas.
    """

    findings: list[str] = []
    for path in workflow_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            match = RUNS_ON_PATTERN.match(line)
            if not match:
                index += 1
                continue

            value = match.group("value").strip()
            if value and _contains_self_hosted(value):
                findings.append(f"{path.relative_to(root)}:{index + 1}: {line.strip()}")
                index += 1
                continue

            if not value:
                key_indent = len(match.group("indent"))
                cursor = index + 1
                while cursor < len(lines):
                    continuation = lines[cursor]
                    stripped = continuation.strip()
                    if not stripped or stripped.startswith("#"):
                        cursor += 1
                        continue

                    continuation_indent = len(continuation) - len(continuation.lstrip())
                    if continuation_indent <= key_indent:
                        break

                    if _contains_self_hosted(stripped):
                        findings.append(
                            f"{path.relative_to(root)}:{cursor + 1}: {stripped}"
                        )
                    cursor += 1
                index = cursor
                continue

            index += 1

    return findings


def load_policy(root: Path, policy_path: Path) -> dict:
    full_path = root / policy_path
    if not full_path.exists():
        return {
            "self_hosted_allowed": False,
            "approved_workflows": [],
            "required_adr": None,
        }
    return json.loads(full_path.read_text(encoding="utf-8"))


def validate(root: Path, policy_path: Path) -> tuple[bool, dict]:
    findings = find_self_hosted_usages(root)
    policy = load_policy(root, policy_path)
    allowed = bool(policy.get("self_hosted_allowed", False))
    approved_workflows = set(policy.get("approved_workflows", []))
    required_adr = policy.get("required_adr")

    violations: list[str] = []
    if findings and not allowed:
        violations.extend(findings)
    elif findings:
        if not required_adr:
            violations.append("Policy permits self-hosted runners but required_adr is missing")
        elif not (root / required_adr).exists():
            violations.append(f"Required ADR not found: {required_adr}")

        for finding in findings:
            workflow = finding.split(":", 1)[0]
            if workflow not in approved_workflows:
                violations.append(f"Workflow not allowlisted: {workflow}")

    result = {
        "status": "pass" if not violations else "fail",
        "self_hosted_usages": findings,
        "violations": violations,
        "policy": policy,
    }
    return not violations, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--policy",
        default=".github/self-hosted-runner-policy.json",
        help="Policy path relative to repository root",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    ok, result = validate(root, Path(args.policy))
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
