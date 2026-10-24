#!/usr/bin/env python3
"""Bloqueia uso não governado de self-hosted runners em workflows GitHub Actions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

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
                findings.append(f"{path.relative_to(root).as_posix()}:{index + 1}: {line.strip()}")
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
                            f"{path.relative_to(root).as_posix()}:{cursor + 1}: {stripped}"
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


def _profile_job_blocks(raw: str, label: str) -> list[str]:
    """Return YAML job blocks whose literal runs-on line selects ``label``."""

    lines = raw.splitlines()
    job_header = re.compile(r"^  [A-Za-z0-9_-]+:\s*(?:#.*)?$")
    selected: dict[int, str] = {}
    for index, line in enumerate(lines):
        match = RUNS_ON_PATTERN.match(line)
        if not match or label not in match.group("value"):
            continue
        start = index
        while start >= 0 and not job_header.match(lines[start]):
            start -= 1
        if start < 0:
            continue
        end = start + 1
        while end < len(lines) and not job_header.match(lines[end]):
            end += 1
        selected[start] = "\n".join(lines[start:end])
    return list(selected.values())


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

    portable = policy.get("portable_dev_runner_contract", {})
    if isinstance(portable, dict) and portable:
        preflight_action = str(portable.get("preflight_action", ""))
        forbidden = [str(item) for item in portable.get("forbidden_hostnames", [])]
        profile_labels = portable.get("profile_labels", {})
        workflow_profiles = portable.get("workflow_profiles", {})
        if not isinstance(profile_labels, dict) or not profile_labels:
            violations.append("Portable DEV profile labels are missing")
            profile_labels = {}
        if not isinstance(workflow_profiles, dict) or not workflow_profiles:
            violations.append("Portable DEV workflow profiles are missing")
            workflow_profiles = {}
        known_labels = {str(label) for label in profile_labels.values() if label}
        for workflow, profile in workflow_profiles.items():
            path = root / str(workflow)
            if not path.is_file():
                violations.append(f"Portable DEV workflow not found: {workflow}")
                continue
            raw = path.read_text(encoding="utf-8")
            required_label = str(profile_labels.get(str(profile), ""))
            if not required_label:
                violations.append(f"Portable DEV profile label unknown: {workflow}:{profile}")
                continue
            profile_jobs = _profile_job_blocks(raw, required_label)
            if not profile_jobs:
                violations.append(f"Portable DEV profile label missing: {workflow}:{profile}")
            for job in profile_jobs:
                for incompatible_label in known_labels - {required_label}:
                    if incompatible_label in job:
                        violations.append(
                            f"Portable DEV incompatible profile label: {workflow}:{incompatible_label}"
                        )
                if f"uses: {preflight_action}" not in job:
                    violations.append(f"Portable DEV job without preflight: {workflow}")
                for hostname in forbidden:
                    if hostname and hostname.casefold() in job.casefold():
                        violations.append(f"Fixed runner hostname forbidden: {workflow}")
                if portable.get("forbid_fixed_runner_id") and re.search(
                    r"\brunner_id\s*[:=]\s*[0-9]+", job, re.IGNORECASE
                ):
                    violations.append(f"Fixed runner id forbidden: {workflow}")

        registered_workflows = {str(item) for item in workflow_profiles}
        for path in workflow_files(root):
            raw = path.read_text(encoding="utf-8")
            if any(label in raw for label in known_labels):
                relative = str(path.relative_to(root)).replace("\\", "/")
                if relative not in registered_workflows:
                    violations.append(f"Portable DEV workflow profile missing: {relative}")

    result_status = "pass" if not violations else "fail"

    result = {
        "status": result_status,
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
