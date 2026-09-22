"""Guardrail tests for disposable probe pull request bases (P0-A).

Canonical rule (`rules/github-workflow.md`): a disposable probe must never use
the default/protected branch as the pull request base; it must run against an
isolated temporary base anchored to the current SHA and be closed afterwards.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_disposable_probe_base import (
    DEFAULT_POLICY,
    PolicyError,
    evaluate_probe_base,
    load_policy,
    scan_workflows,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "a" * 40


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_policy()


def decide(policy: dict, **overrides):
    payload = {
        "base_ref": "probe-base/token-successor-20260916",
        "head_ref": "probe/token-successor-20260916",
        "source_sha": SOURCE_SHA,
        "base_sha": SOURCE_SHA,
        "probe_class": "disposable",
        "default_branch_protected": True,
        "policy": policy,
    }
    payload.update(overrides)
    return evaluate_probe_base(**payload)


# --- caso positivo -----------------------------------------------------------


def test_isolated_base_anchored_to_source_sha_is_allowed(policy: dict) -> None:
    report = decide(policy)

    assert report["allowed"] is True, report["blocking_issues"]
    assert report["decision"] == "allowed"
    assert report["blocking_issues"] == []
    assert report["cleanup_required"] is True
    assert report["production_touched"] is False


# --- caso negativo deliberado: tentativa de usar a branch padrão -------------


def test_deliberate_attempt_to_use_main_as_base_is_blocked(policy: dict) -> None:
    report = decide(policy, base_ref="main")

    assert report["allowed"] is False
    assert "probe_base_is_protected:main" in report["blocking_issues"]


@pytest.mark.parametrize(
    "base_ref",
    ["main", "refs/heads/main", "origin/main", "master", "release/1.4", "hml", "prod"],
)
def test_every_protected_base_spelling_is_blocked(policy: dict, base_ref: str) -> None:
    report = decide(policy, base_ref=base_ref)

    assert report["allowed"] is False
    assert any(
        item.startswith("probe_base_is_protected") for item in report["blocking_issues"]
    )


# --- demais controles fail-closed --------------------------------------------


def test_base_outside_isolated_namespace_is_blocked(policy: dict) -> None:
    report = decide(policy, base_ref="feature/qualquer-coisa")

    assert report["allowed"] is False
    assert "probe_base_not_isolated:feature/qualquer-coisa" in report["blocking_issues"]


def test_base_not_anchored_to_current_sha_is_blocked(policy: dict) -> None:
    report = decide(policy, base_sha="b" * 40)

    assert report["allowed"] is False
    assert "probe_base_not_anchored_to_source_sha" in report["blocking_issues"]


def test_head_equal_to_base_is_blocked(policy: dict) -> None:
    report = decide(
        policy,
        head_ref="probe-base/token-successor-20260916",
    )

    assert report["allowed"] is False
    assert "probe_head_equals_base" in report["blocking_issues"]


def test_unprotected_default_branch_is_a_governance_blocker(policy: dict) -> None:
    report = decide(policy, default_branch_protected=False)

    assert report["allowed"] is False
    assert "default_branch_without_effective_protection" in report["blocking_issues"]


def test_invalid_source_sha_is_blocked(policy: dict) -> None:
    report = decide(policy, source_sha="HEAD", base_sha="HEAD")

    assert report["allowed"] is False
    assert "probe_source_sha_invalid" in report["blocking_issues"]


def test_unknown_probe_class_is_rejected(policy: dict) -> None:
    with pytest.raises(PolicyError):
        decide(policy, probe_class="permanent")


# --- varredura estática ------------------------------------------------------


def _write_workflow(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


def test_scan_blocks_probe_workflow_targeting_main(
    policy: dict, tmp_path: Path
) -> None:
    _write_workflow(
        tmp_path,
        "fake-token-probe.yml",
        "name: probe\njobs:\n  p:\n    steps:\n"
        '      - run: gh pr create --base main --head probe/x --title t --body b\n',
    )

    report = scan_workflows(policy=policy, workflow_dir=tmp_path)

    assert report["allowed"] is False
    assert report["inspected_workflows"] == ["fake-token-probe.yml"]
    assert {"workflow": "fake-token-probe.yml", "issue": "probe_base_is_protected", "base": "main"} in report["findings"]


def test_scan_blocks_workflow_classified_by_marker(
    policy: dict, tmp_path: Path
) -> None:
    _write_workflow(
        tmp_path,
        "descartavel.yml",
        "name: descartavel\nenv:\n  REQSYS_PROBE_CLASS: disposable\njobs:\n  p:\n"
        "    steps:\n      - run: gh pr create --base main --head x/y\n",
    )

    report = scan_workflows(policy=policy, workflow_dir=tmp_path)

    assert report["allowed"] is False
    assert "probe_base_is_protected" in report["blocking_issues"]


def test_scan_allows_isolated_probe_base(policy: dict, tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ok-probe.yml",
        "name: probe\njobs:\n  p:\n    steps:\n"
        '      - run: gh pr create --base probe-base/x --head probe/y\n',
    )

    report = scan_workflows(policy=policy, workflow_dir=tmp_path)

    assert report["allowed"] is True, report["findings"]


def test_scan_ignores_non_probe_workflow_targeting_main(
    policy: dict, tmp_path: Path
) -> None:
    _write_workflow(
        tmp_path,
        "entrega-governada.yml",
        "name: entrega\njobs:\n  p:\n    steps:\n"
        '      - run: gh pr create --base main --head feat/x\n',
    )

    report = scan_workflows(policy=policy, workflow_dir=tmp_path)

    assert report["allowed"] is True, report["findings"]


def test_scan_of_repository_workflows_is_clean(policy: dict) -> None:
    report = scan_workflows(policy=policy)

    assert report["allowed"] is True, report["findings"]


# --- política versionada -----------------------------------------------------


def test_versioned_policy_declares_protected_default_branch() -> None:
    payload = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))

    assert payload["default_branch"] == "main"
    assert "main" in payload["protected_branches"]
    assert payload["require_source_sha_anchor"] is True
    assert payload["require_cleanup_after_evidence"] is True
    assert payload["isolated_base_prefixes"]
