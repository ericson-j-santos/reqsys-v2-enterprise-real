#!/usr/bin/env python3
"""Canonical guardrail for disposable probe pull requests (P0-A).

Governance rule (`rules/github-workflow.md`): a disposable probe — one that
deliberately induces failure, autocorrection or automatic mutation — must never
use the default/protected branch as the pull request base. It must create an
isolated temporary base from the current SHA, run against that base and be
closed once the evidence is collected.

Two enforcement modes:

``decide``
    Fail-closed decision for a concrete probe pull request request.

``scan``
    Static repository scan that blocks any workflow classified as a disposable
    probe from opening a pull request against the default/protected branch.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "governance" / "probe-base-policy.json"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BASE_FLAG_PATTERN = re.compile(
    r"--base[= ]+[\"']?\$?\{?\{?\s*([A-Za-z0-9_./${}\[\]'\" -]+?)\s*\}?\}?[\"']?(?:\s|\\|$)"
)


class PolicyError(ValueError):
    """Raised when the guardrail cannot be evaluated."""


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    if not path.exists():
        raise PolicyError(f"probe_base_policy_missing:{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_ref(ref: str) -> str:
    value = (ref or "").strip()
    for prefix in ("refs/heads/", "refs/remotes/origin/", "origin/"):
        value = value.removeprefix(prefix)
    return value


def _is_protected(ref: str, policy: dict[str, Any]) -> bool:
    candidates: Iterable[str] = [
        policy.get("default_branch", "main"),
        *policy.get("protected_branches", []),
    ]
    return any(fnmatch.fnmatch(ref, str(pattern)) for pattern in candidates if pattern)


def _has_isolated_prefix(ref: str, prefixes: Iterable[str]) -> bool:
    return any(ref.startswith(str(prefix)) for prefix in prefixes if prefix)


def evaluate_probe_base(
    *,
    base_ref: str,
    head_ref: str,
    source_sha: str,
    base_sha: str,
    probe_class: str,
    default_branch_protected: bool,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Return a fail-closed decision for one disposable probe pull request."""
    base = _normalize_ref(base_ref)
    head = _normalize_ref(head_ref)
    blockers: list[str] = []

    if probe_class != "disposable":
        raise PolicyError(f"probe_class_unsupported:{probe_class}")

    if not base:
        blockers.append("probe_base_missing")
    if not head:
        blockers.append("probe_head_missing")

    if base and _is_protected(base, policy):
        blockers.append(f"probe_base_is_protected:{base}")
    if base and not _has_isolated_prefix(base, policy.get("isolated_base_prefixes", [])):
        blockers.append(f"probe_base_not_isolated:{base}")
    if head and not _has_isolated_prefix(head, policy.get("isolated_head_prefixes", [])):
        blockers.append(f"probe_head_not_isolated:{head}")
    if base and head and base == head:
        blockers.append("probe_head_equals_base")

    if policy.get("require_source_sha_anchor", True):
        if not SHA_PATTERN.match((source_sha or "").strip().lower()):
            blockers.append("probe_source_sha_invalid")
        elif (base_sha or "").strip().lower() != source_sha.strip().lower():
            blockers.append("probe_base_not_anchored_to_source_sha")

    # Uma branch padrão sem proteção efetiva não é barreira: `draft`, texto
    # "NUNCA MERGEAR" e checks são sinalização, não enforcement.
    if not default_branch_protected:
        blockers.append("default_branch_without_effective_protection")

    blockers = sorted(set(blockers))
    return {
        "schema_version": "1.0.0",
        "contract": "disposable-probe-base-guardrail",
        "mode": "decide",
        "decision": "allowed" if not blockers else "blocked",
        "allowed": not blockers,
        "base_ref": base,
        "head_ref": head,
        "source_sha": (source_sha or "").strip().lower(),
        "base_sha": (base_sha or "").strip().lower(),
        "probe_class": probe_class,
        "default_branch": policy.get("default_branch", "main"),
        "default_branch_protected": bool(default_branch_protected),
        "cleanup_required": bool(policy.get("require_cleanup_after_evidence", True)),
        "production_touched": False,
        "blocking_issues": blockers,
    }


def _workflow_is_disposable_probe(name: str, content: str, policy: dict[str, Any]) -> bool:
    if any(marker in content for marker in policy.get("probe_classification_markers", [])):
        return True
    return "probe" in name.lower()


def _creates_pull_request(content: str, policy: dict[str, Any]) -> bool:
    return any(
        marker in content for marker in policy.get("pull_request_creation_markers", [])
    )


def _declared_bases(content: str) -> list[str]:
    return [match.strip().strip("\"'") for match in BASE_FLAG_PATTERN.findall(content)]


def scan_workflows(
    *,
    policy: dict[str, Any],
    workflow_dir: Path = WORKFLOW_DIR,
) -> dict[str, Any]:
    """Block disposable probe workflows that open PRs against a protected base."""
    findings: list[dict[str, Any]] = []
    inspected: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml")):
        content = path.read_text(encoding="utf-8")
        if not _workflow_is_disposable_probe(path.name, content, policy):
            continue
        if not _creates_pull_request(content, policy):
            continue
        inspected.append(path.name)
        bases = _declared_bases(content)
        if not bases:
            findings.append(
                {
                    "workflow": path.name,
                    "issue": "probe_base_undeclared",
                    "base": None,
                }
            )
            continue
        for base in bases:
            normalized = _normalize_ref(base)
            if _is_protected(normalized, policy):
                findings.append(
                    {
                        "workflow": path.name,
                        "issue": "probe_base_is_protected",
                        "base": normalized,
                    }
                )
            elif not _has_isolated_prefix(
                normalized, policy.get("isolated_base_prefixes", [])
            ) and not normalized.startswith("${"):
                findings.append(
                    {
                        "workflow": path.name,
                        "issue": "probe_base_not_isolated",
                        "base": normalized,
                    }
                )

    return {
        "schema_version": "1.0.0",
        "contract": "disposable-probe-base-guardrail",
        "mode": "scan",
        "decision": "allowed" if not findings else "blocked",
        "allowed": not findings,
        "inspected_workflows": inspected,
        "findings": findings,
        "production_touched": False,
        "blocking_issues": sorted({item["issue"] for item in findings}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["decide", "scan"], default="scan")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--probe-class", default="disposable")
    parser.add_argument(
        "--default-branch-protected",
        choices=["true", "false"],
        default="true",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    policy = load_policy(args.policy)
    if args.mode == "decide":
        report = evaluate_probe_base(
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            source_sha=args.source_sha,
            base_sha=args.base_sha,
            probe_class=args.probe_class,
            default_branch_protected=args.default_branch_protected == "true",
            policy=policy,
        )
    else:
        report = scan_workflows(policy=policy)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
