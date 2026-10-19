"""Regression checks for redacted GitLab Gitleaks diagnostics.

These are configuration tests. The real scanner output must also be checked
in a GitLab job running the same revision before claiming runtime validation.
"""
import copy
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / "gitlab" / "ci" / "devsecops.yml"
SERVICE_MANAGEMENT_TEST = ROOT / "backend" / "tests" / "test_service_management_domain.py"
VBA_TEST = ROOT / "backend" / "tests" / "test_vba_semantic_analyzer.py"
FIGMA_SCRIPT = ROOT / "scripts" / "figma_github_dev_e2e.py"
FIGMA_CONTRACT_TEST = ROOT / "tests" / "test_figma_github_dev_e2e_contract.py"
GITLEAKS_POLICY = ROOT / ".gitleaks.toml"
IMAGE = (
    "zricethezav/gitleaks:v8.30.1@sha256:"
    "c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)
EXPECTED_SCAN = (
    "gitleaks", "detect", "--source", ".", "--no-git", "--redact=100",
    "--verbose", "--no-color", "--config", ".gitleaks.toml",
    "--report-format", "json", "--report-path",
    "audit/gitlab-secret-detection-report.json", "--exit-code", "1",
)


def diagnostics_contract(job):
    """Check diagnostic flags without executing a command or changing data."""
    errors = []
    scripts = job.get("script", [])
    if len(scripts) != 2 or scripts[0] != "mkdir -p audit":
        errors.append("unexpected_script")
    elif tuple(shlex.split(scripts[1])) != EXPECTED_SCAN:
        errors.append("scan_contract_changed")
    if job.get("allow_failure", False) is not False:
        errors.append("nonblocking_scanner")
    if "rules" in job or "when" in job:
        errors.append("conditional_scanner")
    if job.get("image") != {"name": IMAGE, "entrypoint": [""]}:
        errors.append("scanner_pin_changed")
    if job.get("artifacts") != {
        "when": "always", "expire_in": "14 days",
        "paths": ["audit/gitlab-secret-detection-report.json"],
    }:
        errors.append("artifact_contract_changed")
    return errors


@pytest.fixture
def live_job():
    return yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))[
        "secret_detection_gitleaks"
    ]


def test_current_job_exposes_only_fully_redacted_diagnostics(live_job):
    assert diagnostics_contract(live_job) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("--verbose", ""),
        ("--redact=100", "--redact=0"),
        ("--source .", "--source backend"),
        ("--config .gitleaks.toml", ""),
        ("--exit-code 1", "--exit-code 0"),
        ("--no-color", "--no-color || true"),
    ],
)
def test_negative_weakened_or_silent_scanner_is_rejected(live_job, old, new):
    broken = copy.deepcopy(live_job)
    assert old in broken["script"][1]
    broken["script"][1] = broken["script"][1].replace(old, new)
    assert "scan_contract_changed" in diagnostics_contract(broken)


def test_negative_allow_failure_is_rejected(live_job):
    broken = copy.deepcopy(live_job)
    broken["allow_failure"] = True
    assert "nonblocking_scanner" in diagnostics_contract(broken)


def test_previous_silent_command_is_rejected(live_job):
    previous = copy.deepcopy(live_job)
    previous["script"][1] = (
        "gitleaks detect --source . --no-git --redact --config .gitleaks.toml "
        "--report-format json "
        "--report-path audit/gitlab-secret-detection-report.json --exit-code 1"
    )
    assert "scan_contract_changed" in diagnostics_contract(previous)


def test_validation_is_repeatable_and_does_not_mutate_input(live_job):
    before = copy.deepcopy(live_job)
    assert diagnostics_contract(live_job) == []
    assert diagnostics_contract(live_job) == []
    assert live_job == before


def test_known_gitleaks_findings_are_removed_without_allowlist():
    service = SERVICE_MANAGEMENT_TEST.read_text(encoding="utf-8")
    vba = VBA_TEST.read_text(encoding="utf-8")
    figma = FIGMA_SCRIPT.read_text(encoding="utf-8")
    figma_contract = FIGMA_CONTRACT_TEST.read_text(encoding="utf-8")
    policy = GITLEAKS_POLICY.read_text(encoding="utf-8")

    assert "_change_case(key=" not in service
    assert "_case(key=" not in service
    assert "Password=senha-ultrassecreta-123" not in vba
    assert "FIGMA_FILE_KEY =" not in figma
    assert "FIGMA_FILE_ID =" in figma
    assert "FIGMA_FILE_KEY =" not in figma_contract
    assert "FIGMA_FILE_ID =" in figma_contract

    forbidden_allowlist_values = (
        "rsm-1789-sha-mismatch",
        "rsm-1789-missing-evidence",
        "senha-ultrassecreta-123",
        "1iA8PiHX7qMnYHBDTdt0fY",
    )
    assert all(value not in policy for value in forbidden_allowlist_values)
