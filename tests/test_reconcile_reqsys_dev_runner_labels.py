from __future__ import annotations

import copy

import pytest

from scripts.reconcile_reqsys_dev_runner_labels import (
    ReconcileError,
    build_plan,
    verify,
)

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
                "runner_labels": [
                    "self-hosted",
                    "Windows",
                    "X64",
                    "reqsys-dev",
                    "reqsys-dev-base-v1",
                ]
            },
            "runtime": {
                "runner_labels": [
                    "self-hosted",
                    "Windows",
                    "X64",
                    "reqsys-dev",
                    "reqsys-dev-base-v1",
                    "reqsys-dev-runtime-v1",
                ]
            },
        },
    }


def onboarding(profile="base"):
    value = {
        "schema_version": 1,
        "result": f"REQSYS_DEV_RUNNER_{profile.upper()}_PROFILE_CONFIGURED",
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": profile,
        "environment": "dev",
        "source_sha": SHA,
        "manifest_updated": True,
        "runner_env_updated": profile == "base",
        "labels_applied": False,
        "label_reconciliation_required": True,
        "service_restarted": False,
        "canary_dispatched": False,
        "automatic_retry_enabled": False,
        "deploy_performed": False,
        "production_touched": False,
    }
    if profile == "runtime":
        value.update(
            {
                "manifest_scope": "user_local_app_data",
                "manifest_resolution": "runtime_user_manifest_preferred",
                "bootstrap_selector": "pc24x7",
                "runtime_root_valid": True,
                "docker_engine_valid": True,
                "docker_endpoint_class": "local_npipe",
                "runner_registration_valid": True,
                "service_restart_required": False,
                "service_restart_scheduled": False,
            }
        )
    return value


def inventory(labels=None):
    labels = labels or ["self-hosted", "Windows", "X64", "noteri", "reqsys-dev"]
    return {
        "runners": [
            {
                "id": 23,
                "name": "opaque-host",
                "status": "online",
                "busy": False,
                "labels": [{"name": x} for x in labels],
            }
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


def test_plan_supports_pc24x7_bootstrap_capability_without_runner_id_affinity():
    candidate = inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"])
    candidate["runners"][0]["id"] = 91
    plan = build_plan(policy(), candidate, onboarding(), SHA, SHA, "pc24x7")
    assert plan["runner_id"] == 91
    assert plan["selector_label"] == "pc24x7"
    assert plan["desired_labels"] == ["pc24x7", "reqsys-dev", "reqsys-dev-base-v1"]


def test_runtime_plan_is_idle_only_and_adds_cumulative_capabilities():
    candidate = inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"])
    plan = build_plan(
        policy(), candidate, onboarding("runtime"), SHA, SHA, "pc24x7", "runtime"
    )
    assert plan["profile"] == "runtime"
    assert plan["desired_labels"] == [
        "pc24x7",
        "reqsys-dev",
        "reqsys-dev-base-v1",
        "reqsys-dev-runtime-v1",
    ]

    candidate["runners"][0]["busy"] = True
    with pytest.raises(ReconcileError, match="cardinality"):
        build_plan(
            policy(), candidate, onboarding("runtime"), SHA, SHA, "pc24x7", "runtime"
        )


def test_plan_rejects_unapproved_bootstrap_selector():
    with pytest.raises(ReconcileError, match="runner_selector_invalid"):
        build_plan(policy(), inventory(), onboarding(), SHA, SHA, "fixed-host-name")


def test_runtime_plan_rejects_non_pc24x7_selector():
    with pytest.raises(ReconcileError, match="runtime_runner_selector_invalid"):
        build_plan(
            policy(), inventory(), onboarding("runtime"), SHA, SHA, "noteri", "runtime"
        )


def test_plan_rejects_stale_or_unsafe_onboarding_evidence():
    stale = onboarding()
    stale["source_sha"] = "7" * 40
    with pytest.raises(ReconcileError, match="source_sha"):
        build_plan(policy(), inventory(), stale, SHA, SHA)
    unsafe = onboarding()
    unsafe["production_touched"] = True
    with pytest.raises(ReconcileError, match="production_touched"):
        build_plan(policy(), inventory(), unsafe, SHA, SHA)

    invalid_schema = onboarding("runtime")
    invalid_schema["schema_version"] = 2
    with pytest.raises(ReconcileError, match="schema_version"):
        build_plan(
            policy(),
            inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"]),
            invalid_schema,
            SHA,
            SHA,
            "pc24x7",
            "runtime",
        )

    restart_scheduled = onboarding("runtime")
    restart_scheduled["service_restart_scheduled"] = True
    with pytest.raises(ReconcileError, match="service_restart_scheduled"):
        build_plan(
            policy(),
            inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"]),
            restart_scheduled,
            SHA,
            SHA,
            "pc24x7",
            "runtime",
        )


def test_verify_requires_exact_readback_and_emits_sanitized_evidence():
    plan = build_plan(policy(), inventory(), onboarding(), SHA, SHA)
    after = inventory(
        ["self-hosted", "Windows", "X64", "noteri", "reqsys-dev", "reqsys-dev-base-v1"]
    )
    evidence = verify(plan, after)
    assert evidence["result"] == "REQSYS_DEV_RUNNER_BASE_LABELS_RECONCILED"
    assert evidence["labels_applied"] is True
    assert evidence["label_reconciliation_required"] is False
    assert evidence["canary_dispatched"] is False
    assert evidence["production_touched"] is False
    assert "runner_id" not in evidence


def test_runtime_verify_requires_runtime_readback_and_emits_runtime_evidence():
    before = inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"])
    plan = build_plan(
        policy(), before, onboarding("runtime"), SHA, SHA, "pc24x7", "runtime"
    )
    after = inventory(
        [
            "self-hosted",
            "Windows",
            "X64",
            "pc24x7",
            "reqsys-dev",
            "reqsys-dev-base-v1",
            "reqsys-dev-runtime-v1",
        ]
    )
    evidence = verify(plan, after)
    assert evidence["result"] == "REQSYS_DEV_RUNNER_RUNTIME_LABELS_RECONCILED"
    assert evidence["profile"] == "runtime"
    assert evidence["production_touched"] is False


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [("status", "offline", "offline"), ("busy", True, "busy")],
)
def test_verify_rejects_runner_that_is_not_online_and_idle(field, value, reason):
    before = inventory(["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"])
    plan = build_plan(
        policy(), before, onboarding("runtime"), SHA, SHA, "pc24x7", "runtime"
    )
    after = inventory(
        [
            "self-hosted",
            "Windows",
            "X64",
            "pc24x7",
            "reqsys-dev",
            "reqsys-dev-base-v1",
            "reqsys-dev-runtime-v1",
        ]
    )
    after["runners"][0][field] = value
    with pytest.raises(ReconcileError, match=reason):
        verify(plan, after)


def test_verify_rejects_specialized_or_missing_labels():
    plan = build_plan(policy(), inventory(), onboarding(), SHA, SHA)
    wrong = inventory(
        [
            "self-hosted",
            "Windows",
            "X64",
            "noteri",
            "reqsys-dev",
            "reqsys-dev-runtime-v1",
        ]
    )
    with pytest.raises(ReconcileError, match="readback"):
        verify(plan, wrong)
