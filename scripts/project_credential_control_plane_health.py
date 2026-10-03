#!/usr/bin/env python3
"""Projeta a saúde do Credential & Environment Control Plane sem persistir valores secretos.

Reutiliza evidências sanitizadas do coletor Fly existente e aceita observações
metadata-only de outros provedores. Valores de credenciais nunca são lidos nem gravados.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROL_PLANE = ROOT / "config" / "credential-control-plane.json"
DEFAULT_ENVIRONMENTS = ROOT / "infra" / "fly-environments.json"
DEPLOYED_SECRET_STATES = {"deployed", "complete", "ready", "active"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: raiz JSON deve ser objeto")
    return payload


def _safe_reference_records(records: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(records, list):
        return result
    for item in records:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("reference") or "").strip()
        if not name:
            continue
        status = str(
            item.get("deployment_status") or item.get("status") or "unknown"
        ).strip().lower()
        result[name] = status
    return result


def _index_fly_states(paths: list[Path]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = load_json(path)
        if payload.get("secret_values_persisted") is True:
            raise ValueError(f"{path}: evidência insegura; valores secretos persistidos")
        environment = str(payload.get("environment") or "").strip()
        if environment:
            states[environment] = payload
    return states


def _index_provider_observations(
    paths: list[Path],
) -> dict[tuple[str, str], dict[str, Any]]:
    observations: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        payload = load_json(path)
        if payload.get("secret_values_exposed") is True:
            raise ValueError(f"{path}: evidência insegura; valores secretos expostos")
        provider = str(payload.get("provider") or "").strip()
        environment = str(payload.get("environment") or "").strip()
        if provider and environment:
            observations[(provider, environment)] = payload
    return observations


def _observe_fly_reference(
    state: dict[str, Any] | None, reference: str
) -> tuple[str, str]:
    if not state:
        return "UNKNOWN", "fly_state_missing"

    api = state.get("api") if isinstance(state.get("api"), dict) else {}
    commands = api.get("commands") if isinstance(api.get("commands"), dict) else {}
    secret_command = (
        commands.get("secrets") if isinstance(commands.get("secrets"), dict) else {}
    )
    if secret_command and secret_command.get("ok") is not True:
        return "UNKNOWN", "fly_secret_inventory_unavailable"

    inventory = _safe_reference_records(api.get("secrets"))
    if reference not in inventory:
        return "MISSING", "reference_not_found"
    deployment_status = inventory[reference]
    if deployment_status in DEPLOYED_SECRET_STATES:
        return "AVAILABLE", f"deployment_status:{deployment_status}"
    return "DEGRADED", f"deployment_status:{deployment_status}"


def _observe_generic_reference(
    observation: dict[str, Any] | None, reference: str
) -> tuple[str, str]:
    if not observation:
        return "UNKNOWN", "provider_observation_missing"
    if observation.get("ok") is False:
        return "UNKNOWN", "provider_observation_unavailable"

    inventory = _safe_reference_records(
        observation.get("references") or observation.get("secrets")
    )
    if reference not in inventory:
        return "MISSING", "reference_not_found"
    status = inventory[reference]
    if status in DEPLOYED_SECRET_STATES | {"valid", "configured", "present"}:
        return "AVAILABLE", f"status:{status}"
    return "DEGRADED", f"status:{status}"


def build_health_report(
    control_plane: dict[str, Any],
    environments: dict[str, Any],
    *,
    fly_states: dict[str, dict[str, Any]] | None = None,
    provider_observations: dict[tuple[str, str], dict[str, Any]] | None = None,
    generated_at_epoch: int | None = None,
) -> dict[str, Any]:
    fly_states = fly_states or {}
    provider_observations = provider_observations or {}

    credentials = {
        str(item.get("credential_id")): item
        for item in control_plane.get("credentials", [])
        if isinstance(item, dict) and item.get("credential_id")
    }
    canonical_envs = list(environments.get("canonical_environments") or [])
    environment_defs = environments.get("environments") or {}

    by_environment: dict[str, dict[str, Any]] = {}
    total_bindings = available = missing = degraded = unknown = 0
    risks: list[str] = []
    bindings_by_env: dict[str, list[dict[str, Any]]] = {
        str(env): [] for env in canonical_envs
    }

    for binding in control_plane.get("bindings", []):
        if not isinstance(binding, dict):
            continue
        environment = str(binding.get("environment") or "")
        if environment in bindings_by_env:
            bindings_by_env[environment].append(binding)

    for environment in canonical_envs:
        rows: list[dict[str, Any]] = []
        for binding in bindings_by_env.get(environment, []):
            credential_id = str(binding.get("credential_id") or "")
            credential = credentials.get(credential_id) or {}
            provider = str(credential.get("provider") or "unknown")
            reference = str(credential.get("secret_reference") or "")
            total_bindings += 1

            if provider == "fly":
                status, reason = _observe_fly_reference(
                    fly_states.get(environment), reference
                )
            else:
                status, reason = _observe_generic_reference(
                    provider_observations.get((provider, environment)), reference
                )

            if status == "AVAILABLE":
                available += 1
            elif status == "MISSING":
                missing += 1
                risks.append(f"{environment}:{credential_id}:required_reference_missing")
            elif status == "DEGRADED":
                degraded += 1
                risks.append(f"{environment}:{credential_id}:reference_degraded")
            else:
                unknown += 1
                risks.append(f"{environment}:{credential_id}:evidence_unavailable")

            rows.append(
                {
                    "credential_id": credential_id,
                    "kind": credential.get("kind"),
                    "provider": provider,
                    "reference": reference,
                    "consumer": binding.get("consumer"),
                    "status": status,
                    "reason": reason,
                }
            )

        env_statuses = {row["status"] for row in rows}
        if "MISSING" in env_statuses or "DEGRADED" in env_statuses:
            env_status = "DEGRADED"
        elif "UNKNOWN" in env_statuses:
            env_status = "EVIDENCE_INCOMPLETE"
        elif rows:
            env_status = "HEALTHY"
        else:
            env_status = "NO_BINDINGS"

        env_cfg = environment_defs.get(environment) or {}
        by_environment[environment] = {
            "status": env_status,
            "api_app": env_cfg.get("api_app"),
            "frontend_app": env_cfg.get("frontend_app"),
            "binding_count": len(rows),
            "bindings": rows,
        }

    if missing or degraded:
        overall = "DEGRADED"
    elif unknown:
        overall = "EVIDENCE_INCOMPLETE"
    elif total_bindings:
        overall = "HEALTHY"
    else:
        overall = "NO_BINDINGS"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-credential-control-plane-health",
        "generated_at_epoch": int(
            generated_at_epoch if generated_at_epoch is not None else time.time()
        ),
        "status": overall,
        "security": {
            "stores_secret_values": False,
            "secret_values_exposed": False,
            "evidence_is_metadata_only": True,
        },
        "summary": {
            "environments_total": len(canonical_envs),
            "bindings_total": total_bindings,
            "available_bindings": available,
            "missing_bindings": missing,
            "degraded_bindings": degraded,
            "unknown_bindings": unknown,
        },
        "providers_cataloged": sorted((control_plane.get("providers") or {}).keys()),
        "environments": by_environment,
        "risks": sorted(set(risks)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-plane", type=Path, default=DEFAULT_CONTROL_PLANE)
    parser.add_argument("--environments", type=Path, default=DEFAULT_ENVIRONMENTS)
    parser.add_argument("--fly-state", action="append", type=Path, default=[])
    parser.add_argument("--provider-observation", action="append", type=Path, default=[])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/credential-control-plane/health.json"),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_health_report(
        load_json(args.control_plane),
        load_json(args.environments),
        fly_states=_index_fly_states(args.fly_state),
        provider_observations=_index_provider_observations(args.provider_observation),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "output": str(args.output), **report["summary"]}, ensure_ascii=False))
    if args.strict and report["status"] != "HEALTHY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
