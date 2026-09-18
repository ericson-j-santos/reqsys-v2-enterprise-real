#!/usr/bin/env python3
"""Atualiza somente a API DEV do ReqSys no projeto PC24x7, com rollback.

O script exige uma source tree limpa no SHA esperado, reutiliza os overrides
operacionais já provisionados e nunca lê o conteúdo dos arquivos de segredo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

PROJECT = "wt-pc24x7-piloto"
SERVICE = "api"
CONTAINER = "wt-pc24x7-piloto-api-1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DeployError(RuntimeError):
    pass


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise DeployError(f"{cmd[0]}_failed:exit_{result.returncode}")
    return result


def git_text(source: Path, args: list[str]) -> str:
    return run(["git", *args], cwd=source, timeout=60).stdout.strip()


def validate_source(source: Path, expected_sha: str) -> None:
    if not SHA_RE.fullmatch(expected_sha):
        raise DeployError("invalid_expected_sha")
    if git_text(source, ["rev-parse", "HEAD"]) != expected_sha:
        raise DeployError("source_head_mismatch")
    tracked = git_text(source, ["status", "--porcelain=v1", "--untracked-files=no"])
    if tracked:
        raise DeployError("source_tracked_tree_dirty")
    for name in ("docker-compose.yml", "docker-compose.dev.yml"):
        if not (source / name).is_file():
            raise DeployError(f"missing_compose_file:{name}")


def inspect_runtime() -> dict[str, Any]:
    payload = json.loads(run(["docker", "inspect", CONTAINER], timeout=60).stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise DeployError("runtime_inspect_invalid")
    item = payload[0]
    config = item.get("Config") or {}
    labels = config.get("Labels") or {}
    env_map: dict[str, str] = {}
    for raw in config.get("Env") or []:
        if "=" in raw:
            key, value = raw.split("=", 1)
            env_map[key] = value
    return {
        "project": labels.get("com.docker.compose.project"),
        "service": labels.get("com.docker.compose.service"),
        "working_dir": labels.get("com.docker.compose.project.working_dir"),
        "runtime_sha": env_map.get("GITHUB_SHA"),
    }


def compose_up(source: Path, expected_sha: str, overrides: list[Path]) -> None:
    env = dict(os.environ)
    env["GITHUB_SHA"] = expected_sha
    cmd = [
        "docker", "compose", "-p", PROJECT,
        "-f", str(source / "docker-compose.yml"),
        "-f", str(source / "docker-compose.dev.yml"),
    ]
    for override in overrides:
        cmd += ["-f", str(override)]
    cmd += ["up", "-d", "--build", "--no-deps", SERVICE]
    run(cmd, cwd=source, env=env, timeout=600)


def wait_healthy(expected_sha: str, timeout_seconds: int = 240) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        payload = json.loads(run(["docker", "inspect", CONTAINER], timeout=60).stdout)[0]
        config = payload.get("Config") or {}
        env_map = dict(raw.split("=", 1) for raw in config.get("Env") or [] if "=" in raw)
        state = payload.get("State") or {}
        health = state.get("Health") or {}
        last = str(health.get("Status") or state.get("Status") or "unknown").lower()
        if env_map.get("GITHUB_SHA") == expected_sha and last == "healthy":
            mounts = payload.get("Mounts") or []
            secret_ok = any(str(m.get("Destination")) == "/run/secrets/cofre_keyring_passphrase" and m.get("RW") is False for m in mounts)
            data_ok = any(str(m.get("Destination")) == "/data" and str(m.get("Type")) == "volume" and m.get("RW") is True for m in mounts)
            if not secret_ok or not data_ok:
                raise DeployError("runtime_security_mount_contract_failed")
            labels = config.get("Labels") or {}
            if labels.get("com.docker.compose.project") != PROJECT or labels.get("com.docker.compose.service") != SERVICE:
                raise DeployError("runtime_compose_identity_mismatch")
            return {
                "runtime_sha": expected_sha,
                "health": last,
                "secret_mount_read_only": True,
                "data_volume_persistent": True,
            }
        time.sleep(3)
    raise DeployError(f"runtime_health_timeout:{last}")


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--admin-override", type=Path, required=True)
    parser.add_argument("--teams-override", type=Path, required=True)
    parser.add_argument("--cofre-override", type=Path, required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    source = args.source_root.resolve()
    overrides = [args.admin_override.resolve(), args.teams_override.resolve(), args.cofre_override.resolve()]
    for override in overrides:
        if not override.is_file():
            raise SystemExit(f"override_missing:{override.name}")

    previous = inspect_runtime()
    if previous.get("project") != PROJECT or previous.get("service") != SERVICE:
        raise SystemExit("unexpected_current_runtime")

    deployed = False
    rollback = {"attempted": False, "ok": None}
    try:
        validate_source(source, args.expected_sha)
        compose_up(source, args.expected_sha, overrides)
        deployed = True
        observed = wait_healthy(args.expected_sha)
        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-pc24x7-dev-api-deploy",
            "ok": True,
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "previous_sha": previous.get("runtime_sha"),
            "expected_sha": args.expected_sha,
            "observed": observed,
            "rollback": rollback,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        write_evidence(args.evidence_file, payload)
        print(json.dumps(payload))
        return 0
    except Exception as exc:
        if deployed and previous.get("working_dir") and previous.get("runtime_sha"):
            rollback["attempted"] = True
            try:
                old_source = Path(str(previous["working_dir"]))
                validate_source(old_source, str(previous["runtime_sha"]))
                compose_up(old_source, str(previous["runtime_sha"]), overrides)
                wait_healthy(str(previous["runtime_sha"]))
                rollback["ok"] = True
            except Exception:
                rollback["ok"] = False
        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-pc24x7-dev-api-deploy",
            "ok": False,
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "expected_sha": args.expected_sha,
            "error": str(exc),
            "rollback": rollback,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        write_evidence(args.evidence_file, payload)
        print(json.dumps(payload), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
