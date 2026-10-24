from __future__ import annotations

import copy

import pytest

from scripts.reconcile_reqsys_dev_runner_labels import ReconcileError, build_plan, verify


SHA = "8" * 40


def policy():
    return {
        "pool": "reqsys-dev-pc-pool-v1",
        "environment": "dev",
        "required_safeguards": {
            "hml_enabled": False,
            "stg_enabled": False,
            "production_enabled": False,
            "automatic_retry_enabled": False,
        },
        "profiles": {
            "base": {
                "runner_labels": ["self-hosted", "Windows", "X64", "reqsys-dev", "reqsys-dev-base-v1"]
            }
        },
    }


def onboarding():
    return {
        "result": "REQSYS_DEV_RUNNER_BASE_PROFILE_CONFIGURED",
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": "base",
        "environment": "dev",
        "source_sha": SHA,
        "manifest_updated": True,
        "runner_env_updated": True,
        "labels_applied": False,
        "label_reconciliation_required": True,
        "service_restarted": False,
        "canary_dispatched": False,
        "automatic_retry_enabled": False,
        "deploy_performed": False,
        "production_touched": False,
    }


def inventory(labels=None):
    labels = labels or ["self-hosted", "Windows", "X64", "noteri", "reqsys-dev"]
    return {
        "runners": [
            {"id": 23, "name": "opaque-host", "status": "online", "busy": False, "labels": [{"name": x} for x in labels]}
        ]
    }


def test_plan_preserves_unmanaged_labels_and_adds_only_base_capability():
    plan = build_plan(policy(), inventory(), onboarding(), SHA, SHA)
    assert plan["runner_id"] == 23
    assert plan["desired_labels"] == ["noteri", "reqsys-dev", "reqsys-dev-base-v1"]
    assert "reqsys-dev-runtime-v1" not in plan["desired_labels"]
    assert plan["production_touched"] is False


def test_plan_rejects_missing_or_ambiguous_noteri_runner():
    with pytest.raises(ReconcileError, match="cardinality"):
        build_plan(policy(), {"runners": []}, onboarding(), SHA, SHA)
    ambiguous = inventory()
    ambiguous["runners"].append(copy.deepcopy(ambiguous["runners"][0]) | {"id": 24})
    with pytest.raises(ReconcileError, match="cardinality"):
        build_plan(policy(), ambiguous, onboarding(), SHA, SHA)


def test_plan_rejects_stale_or_unsafe_onboarding_evidence():
    stale = onboarding()
    stale["source_sha"] = "7" * 40
    with pytest.raises(ReconcileError, match="source_sha"):
        build_plan(policy(), inventory(), stale, SHA, SHA)
    unsafe = onboarding()
    unsafe["production_touched"] = True
    with pytest.raises(ReconcileError, match="production_touched"):
        build_plan(policy(), inventory(), unsafe, SHA, SHA)


def test_verify_requires_exact_readback_and_emits_sanitized_evidence():
    plan = build_plan(policy(), inventory(), onboarding(), SHA, SHA)
    after = inventory(["self-hosted", "Windows", "X64", "noteri", "reqsys-dev", "reqsys-dev-base-v1"])
    evidence = verify(plan, after)
    assert evidence["result"] == "REQSYS_DEV_RUNNER_BASE_LABELS_RECONCILED"
    assert evidence["labels_applied"] is True
    assert evidence["label_reconciliation_required"] is False
    assert evidence["canary_dispatched"] is False
    assert evidence["production_touched"] is False
    assert "runner_id" not in evidence


def test_verify_rejects_specialized_or_missing_labels():
    plan = build_plan(policy(), inventory(), onboarding(), SHA, SHA)
    wrong = inventory(["self-hosted", "Windows", "X64", "noteri", "reqsys-dev", "reqsys-dev-runtime-v1"])
    with pytest.raises(ReconcileError, match="readback"):
        verify(plan, wrong)
