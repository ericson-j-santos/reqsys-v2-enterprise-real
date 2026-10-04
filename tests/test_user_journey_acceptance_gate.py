import json
from pathlib import Path

import pytest

from scripts.user_journey_acceptance_gate import evaluate


@pytest.fixture
def policy():
    return json.loads(Path("config/user-journey-acceptance-policy.json").read_text(encoding="utf-8"))


def _stage(*, real=False, mocked=False, status="passed", evidence="run://evidence"):
    return {
        "status": status,
        "real": real,
        "mocked": mocked,
        "evidence": evidence,
    }


def test_acceptance_is_100_only_when_all_real_stages_pass(policy):
    evidence = {
        "feature": "wsjf_planner_excel_simples",
        "environment": "dev",
        "stages": {
            "automated_tests": _stage(),
            "real_deploy": _stage(real=True),
            "live_browser_no_mocks": _stage(real=True),
            "real_external_integrations": _stage(real=True),
            "business_effect": _stage(real=True),
        },
    }

    result = evaluate(evidence, policy)

    assert result["accepted"] is True
    assert result["one_hundred_percent_allowed"] is True
    assert result["acceptance_percent"] == 100.0
    assert result["blocking_issues"] == []


def test_missing_business_effect_blocks_100_percent(policy):
    evidence = {
        "feature": "wsjf_planner_excel_simples",
        "environment": "dev",
        "stages": {
            "automated_tests": _stage(),
            "real_deploy": _stage(real=True),
            "live_browser_no_mocks": _stage(real=True),
            "real_external_integrations": _stage(real=True),
            "business_effect": _stage(real=True, status="pending", evidence="issue://1413"),
        },
    }

    result = evaluate(evidence, policy)

    assert result["accepted"] is False
    assert result["one_hundred_percent_allowed"] is False
    assert result["acceptance_percent"] == 80.0
    assert result["acceptance_status"] == "quality_blocked"
    assert any("Efeito de negócio" in item for item in result["blocking_issues"])


def test_mocked_browser_can_never_be_used_as_real_acceptance(policy):
    evidence = {
        "feature": "feature_x",
        "environment": "dev",
        "stages": {
            "automated_tests": _stage(),
            "real_deploy": _stage(real=True),
            "live_browser_no_mocks": _stage(real=True, mocked=True),
            "real_external_integrations": _stage(real=True),
            "business_effect": _stage(real=True),
        },
    }

    result = evaluate(evidence, policy)

    assert result["accepted"] is False
    assert result["acceptance_percent"] == 80.0
    assert "mocked_evidence_forbidden" in result["stages"]["live_browser_no_mocks"]["reasons"]


def test_real_stage_without_real_flag_fails_closed(policy):
    evidence = {
        "feature": "feature_x",
        "environment": "dev",
        "stages": {
            "automated_tests": _stage(),
            "real_deploy": _stage(real=False),
            "live_browser_no_mocks": _stage(real=True),
            "real_external_integrations": _stage(real=True),
            "business_effect": _stage(real=True),
        },
    }

    result = evaluate(evidence, policy)

    assert result["accepted"] is False
    assert "real_evidence_required" in result["stages"]["real_deploy"]["reasons"]


def test_evidence_reference_is_mandatory(policy):
    evidence = {
        "feature": "feature_x",
        "environment": "dev",
        "stages": {
            "automated_tests": _stage(evidence=""),
            "real_deploy": _stage(real=True),
            "live_browser_no_mocks": _stage(real=True),
            "real_external_integrations": _stage(real=True),
            "business_effect": _stage(real=True),
        },
    }

    result = evaluate(evidence, policy)

    assert result["accepted"] is False
    assert "evidence_reference_missing" in result["stages"]["automated_tests"]["reasons"]
