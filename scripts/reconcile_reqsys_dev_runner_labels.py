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
    evidence: dict[str, Any], expected_sha: str, profile: str
) -> None:
    if profile not in {"base", "runtime"}:
        raise ReconcileError("profile_invalid")
    required = {
        "schema_version": 1,
        "result": f"REQSYS_DEV_RUNNER_{profile.upper()}_PROFILE_CONFIGURED",
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": profile,
        "environment": "dev",
        "source_sha": expected_sha,
        "manifest_updated": True,
        "labels_applied": False,
        "label_reconciliation_required": True,
        "service_restarted": False,
        "canary_dispatched": False,
        "automatic_retry_enabled": False,
        "deploy_performed": False,
        "production_touched": False,
    }
    if profile == "base":
        required["runner_env_updated"] = True
    else:
        required.update(
            {
                "manifest_scope": "user_local_app_data",
                "manifest_resolution": "runtime_user_manifest_preferred",
                "bootstrap_selector": "pc24x7",
                "runner_env_updated": False,
                "runtime_root_valid": True,
                "docker_engine_valid": True,
                "docker_endpoint_class": "local_npipe",
                "runner_registration_valid": True,
                "service_restart_required": False,
                "service_restart_scheduled": False,
            }
        )
    for key, expected in required.items():
        if evidence.get(key) != expected:
            raise ReconcileError(f"onboarding_evidence_invalid:{key}")


def desired_profile_labels(policy: dict[str, Any], profile_name: str) -> list[str]:
    if (
        policy.get("environment") != "dev"
        or policy.get("pool") != "reqsys-dev-pc-pool-v1"
    ):
        raise ReconcileError("policy_scope_invalid")
    safeguards = policy.get("required_safeguards")
    if not isinstance(safeguards, dict) or any(
        safeguards.get(key) is not False
        for key in (
            "hml_enabled",
            "stg_enabled",
            "production_enabled",
            "automatic_retry_enabled",
        )
    ):
        raise ReconcileError("policy_safeguards_invalid")
    if profile_name not in {"base", "runtime"}:
        raise ReconcileError("profile_invalid")
    profile = (policy.get("profiles") or {}).get(profile_name)
    raw = profile.get("runner_labels") if isinstance(profile, dict) else None
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(item, str) and item for item in raw)
    ):
        raise ReconcileError(f"{profile_name}_profile_labels_invalid")
    normalized = {item.casefold() for item in raw}
    if not {
        "self-hosted",
        "windows",
        "x64",
        "reqsys-dev",
        "reqsys-dev-base-v1",
    }.issubset(normalized):
        raise ReconcileError(f"{profile_name}_profile_labels_incomplete")
    if profile_name == "runtime" and "reqsys-dev-runtime-v1" not in normalized:
        raise ReconcileError("runtime_profile_labels_incomplete")
    if "reqsys-dev-ollama-v1" in normalized:
        raise ReconcileError(f"{profile_name}_profile_scope_invalid")
    if profile_name == "base" and "reqsys-dev-runtime-v1" in normalized:
        raise ReconcileError("base_profile_scope_invalid")
    return list(raw)


def build_plan(
    policy: dict[str, Any],
    inventory: dict[str, Any],
    onboarding: dict[str, Any],
    expected_sha: str,
    onboarding_sha: str,
    selector_label: str = "noteri",
    profile: str = "base",
) -> dict[str, Any]:
    if len(expected_sha) != 40 or any(
        char not in "0123456789abcdef" for char in expected_sha
    ):
        raise ReconcileError("expected_sha_invalid")
    if len(onboarding_sha) != 40 or any(
        char not in "0123456789abcdef" for char in onboarding_sha
    ):
        raise ReconcileError("onboarding_sha_invalid")
    validate_onboarding(onboarding, onboarding_sha, profile)
    selector_label = selector_label.casefold()
    if selector_label not in SELECTOR_LABELS:
        raise ReconcileError("runner_selector_invalid")
    if profile == "runtime" and selector_label != "pc24x7":
        raise ReconcileError("runtime_runner_selector_invalid")
    selector = {"self-hosted", "windows", "x64", selector_label, "reqsys-dev"}
    profile_labels = desired_profile_labels(policy, profile)
    runners = inventory.get("runners")
    if not isinstance(runners, list):
        raise ReconcileError("runner_inventory_invalid")
    candidates: list[tuple[dict[str, Any], list[str]]] = []
    for runner in runners:
        if (
            not isinstance(runner, dict)
            or str(runner.get("status") or "").casefold() != "online"
            or runner.get("busy") is not False
        ):
            continue
        current = labels(runner)
        if selector.issubset({item.casefold() for item in current}):
            candidates.append((runner, current))
    if len(candidates) != 1:
        raise ReconcileError(
            f"runner_selector_cardinality_invalid:{selector_label}:{len(candidates)}"
        )
    runner, current = candidates[0]
    runner_id = runner.get("id")
    if not isinstance(runner_id, int) or runner_id < 1:
        raise ReconcileError("runner_id_invalid")
    preserved = [
        item
        for item in current
        if item.casefold() not in DEFAULT_LABELS
        and item.casefold() not in MANAGED_LABELS
    ]
    desired = sorted(
        set(
            preserved
            + [item for item in profile_labels if item.casefold() not in DEFAULT_LABELS]
        ),
        key=str.casefold,
    )
    current_custom = sorted(
        [item for item in current if item.casefold() not in DEFAULT_LABELS],
        key=str.casefold,
    )
    return {
        "schema_version": 1,
        "runner_id": runner_id,
        "desired_labels": desired,
        "mutation_required": current_custom != desired,
        "expected_sha": expected_sha,
        "onboarding_sha": onboarding_sha,
        "profile": profile,
        "selector_label": selector_label,
        "environment": "dev",
        "production_touched": False,
    }


def verify(plan: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    runner_id = plan.get("runner_id")
    desired = plan.get("desired_labels")
    if not isinstance(runner_id, int) or not isinstance(desired, list):
        raise ReconcileError("reconciliation_plan_invalid")
    matches = [
        runner
        for runner in inventory.get("runners") or []
        if runner.get("id") == runner_id
    ]
    if len(matches) != 1:
        raise ReconcileError("runner_readback_missing")
    runner = matches[0]
    if str(runner.get("status") or "").casefold() != "online":
        raise ReconcileError("runner_readback_offline")
    if runner.get("busy") is not False:
        raise ReconcileError("runner_readback_busy")
    current = labels(runner)
    current_custom = sorted(
        [item for item in current if item.casefold() not in DEFAULT_LABELS],
        key=str.casefold,
    )
    if current_custom != sorted(desired, key=str.casefold):
        raise ReconcileError("runner_label_readback_mismatch")
    profile = plan.get("profile")
    if profile not in {"base", "runtime"}:
        raise ReconcileError("reconciliation_profile_invalid")
    normalized = {item.casefold() for item in current_custom}
    if "reqsys-dev-base-v1" not in normalized:
        raise ReconcileError("base_capability_label_missing")
    if profile == "runtime" and "reqsys-dev-runtime-v1" not in normalized:
        raise ReconcileError("runtime_capability_label_missing")
    return {
        "schema_version": 1,
        "result": f"REQSYS_DEV_RUNNER_{profile.upper()}_LABELS_RECONCILED",
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": profile,
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
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--policy", type=Path, required=True)
    plan_parser.add_argument("--inventory", type=Path, required=True)
    plan_parser.add_argument("--onboarding-evidence", type=Path, required=True)
    plan_parser.add_argument("--expected-sha", required=True)
    plan_parser.add_argument("--onboarding-sha", required=True)
    plan_parser.add_argument(
        "--selector-label", choices=sorted(SELECTOR_LABELS), default="noteri"
    )
    plan_parser.add_argument("--profile", choices=("base", "runtime"), default="base")
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
                args.profile,
            )
        else:
            value = verify(load_object(args.plan), load_object(args.inventory))
        write_json(args.output, value)
        print(json.dumps({"status": "ok", "result": value.get("result", "plan_ready")}))
        return 0
    except Exception as exc:  # noqa: BLE001 - external evidence must fail closed.
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(exc)[:500],
                    "production_touched": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
