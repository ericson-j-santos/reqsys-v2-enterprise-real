#!/usr/bin/env python3
"""Validate that advisory workflows stay outside the pull-request critical path."""

from __future__ import annotations

import sys
from pathlib import Path

MANUAL_ONLY_ADVISORY = (
    ".github/workflows/runtime-risk-scoring.yml",
    ".github/workflows/pr-quality-review.yml",
    ".github/workflows/predictive-regression-guard.yml",
    ".github/workflows/preview-environment-contract.yml",
    ".github/workflows/pr-fast-classifier.yml",
)

POST_CI_ROUTER = ".github/workflows/ci-advisory-router.yml"

FORBIDDEN_REQUIRED_GATE_TOKENS = {
    ".github/workflows/reqsys-required-fast-gate.yml": ["paths:", "paths-ignore:"],
}


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def trigger_block(content: str) -> str:
    return content.split("permissions:", 1)[0]


def main() -> int:
    for path_text in MANUAL_ONLY_ADVISORY:
        path = Path(path_text)
        if not path.exists():
            return fail(f"workflow advisory ausente: {path_text}")
        trigger = trigger_block(path.read_text(encoding="utf-8"))
        if "workflow_dispatch:" not in trigger:
            return fail(f"{path_text}: workflow_dispatch manual ausente")
        if "pull_request:" in trigger:
            return fail(f"{path_text}: report-only ainda materializa no pull_request")

    router = Path(POST_CI_ROUTER)
    if not router.exists():
        return fail(f"router pós-CI ausente: {POST_CI_ROUTER}")
    router_text = router.read_text(encoding="utf-8")
    router_trigger = trigger_block(router_text)
    for token in (
        "workflow_run:",
        "CI — ReqSys v2 Enterprise",
        "types: [completed]",
    ):
        if token not in router_trigger:
            return fail(f"{POST_CI_ROUTER}: contrato pós-CI ausente: {token}")
    for token in (
        "automatic_dispatch: false",
        "critical_path_blocker: false",
        "production_touched: false",
    ):
        if token not in router_text:
            return fail(f"{POST_CI_ROUTER}: guardrail ausente: {token}")
    if "actions: write" in router_text:
        return fail(f"{POST_CI_ROUTER}: não deve possuir actions: write")

    deep = Path(".github/workflows/deep-governance-review.yml")
    deep_trigger = trigger_block(deep.read_text(encoding="utf-8"))
    if "types: [labeled]" not in deep_trigger or "synchronize" in deep_trigger:
        return fail("Deep Governance Review ainda materializa em synchronize")

    for path_text, tokens in FORBIDDEN_REQUIRED_GATE_TOKENS.items():
        path = Path(path_text)
        if not path.exists():
            return fail(f"workflow obrigatório ausente: {path_text}")
        content = path.read_text(encoding="utf-8")
        present = [token for token in tokens if token in content]
        if present:
            return fail(
                f"{path_text}: gate obrigatório não deve ter filtro por path: {present}"
            )

    print("Path-based/advisory workflow router validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
