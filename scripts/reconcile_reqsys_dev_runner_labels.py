#!/usr/bin/env python3
"""Plan and verify fail-closed ReqSys DEV runner label reconciliation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class ReconcileError(RuntimeError):
    pass


DEFAULT_LABELS = {"self-hosted", "windows", "x64"}
MANAGED_LABELS = {
    "reqsys-dev",
    "reqsys-dev-base-v1",
    "reqsys-dev-runtime-v1",
    "reqsys-dev-ollama-v1",
    "reqsys-dev-pool-v1",
    "reqsys-cap-base-v1",
    "reqsys-cap-runtime-v1",
    "reqsys-cap-ollama-v1",
}
SELECTOR_LABELS = {"noteri", "pc24x7"}
SELECTOR_PROFILES = {"noteri": "base", "pc24x7": "runtime"}
PROFILE_RESULTS = {
    "base": {
        "onboarding": "REQSYS_DEV_RUNNER_BASE_PROFILE_CONFIGURED",
        "reconciled": "REQSYS_DEV_RUNNER_BASE_LABELS_RECONCILED",
    },
    "runtime": {
        "onboarding": "REQSYS_DEV_RUNNER_RUNTIME_PROFILE_CONFIGURED",
        "reconciled": "REQSYS_DEV_RUNNER_RUNTIME_LABELS_RECONCILED",
    },
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ReconcileError(f"json_object_required:{path}")
    return value


def labels(runner: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for raw in runner.get("labels") or []:
        value = raw.get("name") if isinstance(raw, dict) else raw
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return sorted(set(result), key=str.casefold)


def validate_onboarding(
    evidence: dict[str, Any], expected_sha: str, selector_label: str
) -> str:
    expected_profile = SELECTOR_PROFILES.get(selector_label)
    if expected_profile is None:
        raise ReconcileError("runner_selector_invalid")
    required = {
        "result": PROFILE_RESULTS[expected_profile]["onboarding"],
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": expected_profile,
        "environment": "dev",
        "source_sha": expected_sha,
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
    for key, expected in required.items():
        if evidence.get(key) != expected:
            raise ReconcileError(f"onboarding_evidence_invalid:{key}")
    if selector_label == "pc24x7":
        pc24x7_required = {
            "bootstrap_selector": "pc24x7",
            "admin_route": "scheduled_task_s4u_highest",
            "admin_secret_supplied": False,
            "service_restart_scheduled": True,
        }
        for key, expected in pc24x7_required.items():
            if evidence.get(key) != expected:
                raise ReconcileError(f"onboarding_evidence_invalid:{key}")
        if not isinstance(evidence.get("runner_instance_id"), str) or not evidence["runner_instance_id"].strip():
            raise ReconcileError("onboarding_evidence_invalid:runner_instance_id")
    return expected_profile


def desired_profile_labels(policy: dict[str, Any], profile_name: str) -> list[str]:
    if policy.get("environment") != "dev" or policy.get("pool") != "reqsys-dev-pc-pool-v1":
        raise ReconcileError("policy_scope_invalid")
    safeguards = policy.get("required_safeguards")
    if not isinstance(safeguards, dict) or any(safeguards.get(key) is not False for key in (
        "hml_enabled", "stg_enabled", "production_enabled", "automatic_retry_enabled"
    )):
        raise ReconcileError("policy_safeguards_invalid")
    if profile_name not in PROFILE_RESULTS:
        raise ReconcileError("profile_scope_invalid")
    profile = (policy.get("profiles") or {}).get(profile_name)
    raw = profile.get("runner_labels") if isinstance(profile, dict) else None
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) and item for item in raw):
        raise ReconcileError(f"{profile_name}_profile_labels_invalid")
    normalized = {item.casefold() for item in raw}
    required = {"self-hosted", "windows", "x64", "reqsys-dev", "reqsys-dev-base-v1"}
    forbidden = {"reqsys-dev-ollama-v1"}
    if profile_name == "runtime":
        required.add("reqsys-dev-runtime-v1")
    else:
        forbidden.add("reqsys-dev-runtime-v1")
    if not required.issubset(normalized):
        raise ReconcileError(f"{profile_name}_profile_labels_incomplete")
    if normalized & forbidden:
        raise ReconcileError(f"{profile_name}_profile_scope_invalid")
    return list(raw)


def build_plan(
    policy: dict[str, Any],
    inventory: dict[str, Any],
    onboarding: dict[str, Any],
    expected_sha: str,
    onboarding_sha: str,
    selector_label: str = "noteri",
) -> dict[str, Any]:
    if len(expected_sha) != 40 or any(char not in "0123456789abcdef" for char in expected_sha):
        raise ReconcileError("expected_sha_invalid")
    if len(onboarding_sha) != 40 or any(char not in "0123456789abcdef" for char in onboarding_sha):
        raise ReconcileError("onboarding_sha_invalid")
    selector_label = selector_label.casefold()
    if selector_label not in SELECTOR_LABELS:
        raise ReconcileError("runner_selector_invalid")
    profile_name = validate_onboarding(onboarding, onboarding_sha, selector_label)
    selector = {"self-hosted", "windows", "x64", selector_label, "reqsys-dev"}
    profile_labels = desired_profile_labels(policy, profile_name)
    runners = inventory.get("runners")
    if not isinstance(runners, list):
        raise ReconcileError("runner_inventory_invalid")
    candidates: list[tuple[dict[str, Any], list[str]]] = []
    for runner in runners:
        if not isinstance(runner, dict) or str(runner.get("status") or "").casefold() != "online":
            continue
        current = labels(runner)
        if selector.issubset({item.casefold() for item in current}):
            candidates.append((runner, current))
    if len(candidates) != 1:
        raise ReconcileError(f"runner_selector_cardinality_invalid:{selector_label}:{len(candidates)}")
    runner, current = candidates[0]
    runner_id = runner.get("id")
    if not isinstance(runner_id, int) or runner_id < 1:
        raise ReconcileError("runner_id_invalid")
    preserved = [
        item for item in current
        if item.casefold() not in DEFAULT_LABELS and item.casefold() not in MANAGED_LABELS
    ]
    desired = sorted(
        set(preserved + [item for item in profile_labels if item.casefold() not in DEFAULT_LABELS]),
        key=str.casefold,
    )
    current_custom = sorted(
        [item for item in current if item.casefold() not in DEFAULT_LABELS], key=str.casefold
    )
    return {
        "schema_version": 1,
        "runner_id": runner_id,
        "desired_labels": desired,
        "mutation_required": current_custom != desired,
        "expected_sha": expected_sha,
        "onboarding_sha": onboarding_sha,
        "profile": profile_name,
        "selector_label": selector_label,
        "environment": "dev",
        "production_touched": False,
    }


def verify(plan: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    runner_id = plan.get("runner_id")
    desired = plan.get("desired_labels")
    profile_name = plan.get("profile")
    if (
        not isinstance(runner_id, int)
        or not isinstance(desired, list)
        or profile_name not in PROFILE_RESULTS
    ):
        raise ReconcileError("reconciliation_plan_invalid")
    matches = [runner for runner in inventory.get("runners") or [] if runner.get("id") == runner_id]
    if len(matches) != 1:
        raise ReconcileError("runner_readback_missing")
    current = labels(matches[0])
    current_custom = sorted(
        [item for item in current if item.casefold() not in DEFAULT_LABELS], key=str.casefold
    )
    if current_custom != sorted(desired, key=str.casefold):
        raise ReconcileError("runner_label_readback_mismatch")
    capability_label = f"reqsys-dev-{profile_name}-v1"
    if capability_label not in {item.casefold() for item in current_custom}:
        raise ReconcileError(f"{profile_name}_capability_label_missing")
    return {
        "schema_version": 1,
        "result": PROFILE_RESULTS[profile_name]["reconciled"],
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": profile_name,
        "environment": "dev",
        "source_sha": plan.get("expected_sha"),
        "onboarding_sha": plan.get("onboarding_sha"),
        "runner_labels": current,
        "labels_applied": True,
        "labels_changed": plan.get("mutation_required") is True,
        "label_reconciliation_required": False,
        "service_restarted": False,
        "canary_dispatched": False,
        "automatic_retry_enabled": False,
        "deploy_performed": False,
        "production_touched": False,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--policy", type=Path, required=True)
    plan_parser.add_argument("--inventory", type=Path, required=True)
    plan_parser.add_argument("--onboarding-evidence", type=Path, required=True)
    plan_parser.add_argument("--expected-sha", required=True)
    plan_parser.add_argument("--onboarding-sha", required=True)
    plan_parser.add_argument("--selector-label", choices=sorted(SELECTOR_LABELS), default="noteri")
    plan_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--plan", type=Path, required=True)
    verify_parser.add_argument("--inventory", type=Path, required=True)
    verify_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            value = build_plan(
                load_object(args.policy),
                load_object(args.inventory),
                load_object(args.onboarding_evidence),
                args.expected_sha,
                args.onboarding_sha,
                args.selector_label,
            )
        else:
            value = verify(load_object(args.plan), load_object(args.inventory))
        write_json(args.output, value)
        print(json.dumps({"status": "ok", "result": value.get("result", "plan_ready")}))
        return 0
    except Exception as exc:  # noqa: BLE001 - external evidence must fail closed.
        print(json.dumps({"status": "blocked", "reason": str(exc)[:500], "production_touched": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
