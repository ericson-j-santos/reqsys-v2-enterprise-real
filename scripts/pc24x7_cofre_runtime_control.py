#!/usr/bin/env python3
"""Controle governado do runtime do Cofre no PC24x7 DEV.

Valida identidade do container, SHA publicado, mount somente leitura da
passphrase e volume persistente antes de permitir restart. Nunca lê o conteúdo
do segredo montado.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

CONTAINER = "wt-pc24x7-piloto-api-1"
PROJECT = "wt-pc24x7-piloto"
SERVICE = "api"
SECRET_TARGET = "/run/secrets/cofre_keyring_passphrase"
DATA_TARGET = "/data"


class RuntimeControlError(RuntimeError):
    pass


def run_docker(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeControlError(f"docker_{args[0]}_failed:exit_{result.returncode}")
    return result


def inspect_container(expected_sha: str) -> dict[str, Any]:
    payload = json.loads(run_docker(["inspect", CONTAINER]).stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise RuntimeControlError("container_inspect_invalid")

    item = payload[0]
    config = item.get("Config") or {}
    labels = config.get("Labels") or {}
    env_map: dict[str, str] = {}
    for raw in config.get("Env") or []:
        if "=" in raw:
            key, value = raw.split("=", 1)
            env_map[key] = value

    if labels.get("com.docker.compose.project") != PROJECT:
        raise RuntimeControlError("compose_project_mismatch")
    if labels.get("com.docker.compose.service") != SERVICE:
        raise RuntimeControlError("compose_service_mismatch")
    if env_map.get("GITHUB_SHA") != expected_sha:
        raise RuntimeControlError("runtime_sha_mismatch")

    mounts = item.get("Mounts") or []
    secret_mount_ok = any(
        str(mount.get("Destination")) == SECRET_TARGET and mount.get("RW") is False
        for mount in mounts
    )
    data_volume_ok = any(
        str(mount.get("Destination")) == DATA_TARGET
        and str(mount.get("Type")) == "volume"
        and mount.get("RW") is True
        for mount in mounts
    )
    if not secret_mount_ok:
        raise RuntimeControlError("cofre_secret_mount_missing_or_writable")
    if not data_volume_ok:
        raise RuntimeControlError("cofre_data_volume_missing")

    state = item.get("State") or {}
    health = state.get("Health") or {}
    return {
        "container": CONTAINER,
        "project": PROJECT,
        "service": SERVICE,
        "runtime_sha": expected_sha,
        "secret_mount_read_only": True,
        "data_volume_persistent": True,
        "health": str(health.get("Status") or state.get("Status") or "unknown").lower(),
        "sensitive_values_exposed": False,
        "production_touched": False,
    }


def wait_healthy(expected_sha: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        evidence = inspect_container(expected_sha)
        last = str(evidence.get("health") or "unknown")
        if last == "healthy":
            return evidence
        time.sleep(2)
    raise RuntimeControlError(f"container_health_timeout:{last}")


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "restart"])
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    try:
        before = inspect_container(args.expected_sha)
        restarted = False
        if args.action == "restart":
            run_docker(["restart", CONTAINER], timeout=120)
            restarted = True
            after = wait_healthy(args.expected_sha, args.timeout)
        else:
            after = before

        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-cofre-pc24x7-runtime-control",
            "ok": True,
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "expected_sha": args.expected_sha,
            "restart_performed": restarted,
            "before": before,
            "after": after,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        write_evidence(args.evidence_file, payload)
        print(json.dumps({
            "ok": True,
            "environment": "dev",
            "runtime_sha": args.expected_sha,
            "restart_performed": restarted,
            "health": after["health"],
            "sensitive_values_exposed": False,
            "production_touched": False,
        }))
        return 0
    except Exception as exc:
        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-cofre-pc24x7-runtime-control",
            "ok": False,
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "expected_sha": args.expected_sha,
            "error": str(exc),
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        write_evidence(args.evidence_file, payload)
        print(json.dumps(payload), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
