from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .maintenance import recover_rdc

VALID_PROFILES = {"NORMAL", "ESTUDO"}
SAFE_TASK_TYPES = {"orchestrator.selftest", "host.rdc.recover.v1"}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_profile_path() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return Path(base) / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"


def resolve_profile(path: Path | None) -> str:
    if path is None or not path.exists():
        return "NORMAL"
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = payload.get("profile")
    if profile not in VALID_PROFILES:
        raise ValueError("invalid host profile")
    return profile


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    raw = None
    headers: dict[str, str] = {}
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=raw, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"control plane unavailable: {type(exc.reason).__name__}") from exc


@dataclass(frozen=True)
class WorkerAgentConfig:
    endpoint: str
    worker_id: str
    roles: list[str]
    controller_version: str
    dispatch_priority: int = 100
    heartbeat_ttl_seconds: int = 120
    heartbeat_interval_seconds: float = 30.0
    poll_interval_seconds: float = 2.0
    lease_seconds: int = 120
    profile_path: Path | None = None


class WorkerAgent:
    def __init__(self, config: WorkerAgentConfig):
        self.config = config
        self.endpoint = config.endpoint.rstrip("/")
        self.device_name = socket.gethostname()

    def heartbeat(self, correlation_id: str) -> dict[str, Any]:
        profile = resolve_profile(self.config.profile_path or default_profile_path())
        status, response = request_json(
            "POST",
            self.endpoint + "/v1/workers/heartbeat",
            {
                "worker_id": self.config.worker_id,
                "device_name": self.device_name,
                "roles": self.config.roles,
                "capabilities": {
                    "dispatch_priority": self.config.dispatch_priority,
                    "python_version": platform.python_version(),
                    "platform": platform.system(),
                    "source": "persistent-worker-agent",
                    "safe_task_types": sorted(SAFE_TASK_TYPES),
                },
                "profile": profile,
                "controller_online": True,
                "auth_valid": True,
                "controller_version": self.config.controller_version,
                "correlation_id": correlation_id,
                "heartbeat_ttl_seconds": self.config.heartbeat_ttl_seconds,
            },
        )
        if status != 200:
            raise RuntimeError(f"heartbeat failed with HTTP {status}")
        return response["worker"]

    def dispatch_pending(self) -> None:
        profile = resolve_profile(self.config.profile_path or default_profile_path())
        if profile != "NORMAL":
            return
        status, _ = request_json(
            "POST",
            self.endpoint + "/v1/dispatch",
            {"lease_seconds": self.config.lease_seconds},
        )
        if status != 200:
            raise RuntimeError(f"dispatch failed with HTTP {status}")

    def assignments(self) -> list[dict[str, Any]]:
        status, response = request_json(
            "GET",
            self.endpoint + f"/v1/workers/{self.config.worker_id}/assignments",
        )
        if status != 200:
            raise RuntimeError(f"assignments failed with HTTP {status}")
        return response.get("items", [])

    def renew(self, item_id: str) -> None:
        status, _ = request_json(
            "POST",
            self.endpoint + f"/v1/work-items/{item_id}/renew",
            {
                "worker_id": self.config.worker_id,
                "lease_seconds": self.config.lease_seconds,
            },
        )
        if status != 200:
            raise RuntimeError(f"lease renewal failed with HTTP {status}")

    def complete(self, item_id: str, result: dict[str, Any]) -> None:
        status, _ = request_json(
            "POST",
            self.endpoint + f"/v1/work-items/{item_id}/complete",
            {"worker_id": self.config.worker_id, "result": result},
        )
        if status != 200:
            raise RuntimeError(f"complete failed with HTTP {status}")

    def fail(self, item_id: str, error: str) -> None:
        status, _ = request_json(
            "POST",
            self.endpoint + f"/v1/work-items/{item_id}/fail",
            {"worker_id": self.config.worker_id, "error": error[:1000]},
        )
        if status != 200:
            raise RuntimeError(f"fail failed with HTTP {status}")

    def execute(self, item: dict[str, Any]) -> dict[str, Any]:
        task_type = item.get("task_type")
        if task_type not in SAFE_TASK_TYPES:
            raise RuntimeError(f"unsupported task_type: {task_type}")
        if task_type == "orchestrator.selftest":
            payload = item.get("payload") or {}
            return {
                "handler": "orchestrator.selftest",
                "worker_id": self.config.worker_id,
                "device_name": self.device_name,
                "correlation_id": item.get("correlation_id"),
                "input": payload.get("input"),
                "observed_at": utc_iso(),
            }
        if task_type == "host.rdc.recover.v1":
            payload = item.get("payload") or {}
            result = recover_rdc(target_host=payload.get("target_host"))
            result.update(
                {
                    "worker_id": self.config.worker_id,
                    "device_name": self.device_name,
                    "correlation_id": item.get("correlation_id"),
                    "observed_at": utc_iso(),
                }
            )
            return result
        raise RuntimeError("unreachable task type")

    def process_one(self) -> dict[str, Any] | None:
        items = self.assignments()
        if not items:
            return None
        item = items[0]
        item_id = item["id"]
        try:
            self.renew(item_id)
            result = self.execute(item)
            self.complete(item_id, result)
            return {"item_id": item_id, "status": "completed", "result": result}
        except Exception as exc:
            try:
                self.fail(item_id, f"{type(exc).__name__}: {exc}")
            except Exception:
                pass
            return {"item_id": item_id, "status": "failed", "error": str(exc)}

    def run_once(self, correlation_id: str) -> dict[str, Any]:
        worker = self.heartbeat(correlation_id)
        self.dispatch_pending()
        outcome = self.process_one()
        return {"worker": worker, "outcome": outcome}

    def run_forever(self) -> None:
        last_heartbeat = 0.0
        backoff = 1.0
        while True:
            try:
                now = time.monotonic()
                if now - last_heartbeat >= self.config.heartbeat_interval_seconds:
                    self.heartbeat(
                        f"worker-{self.config.worker_id}-{int(time.time())}"
                    )
                    last_heartbeat = now
                self.dispatch_pending()
                self.process_one()
                backoff = 1.0
                time.sleep(self.config.poll_interval_seconds)
            except KeyboardInterrupt:
                return
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)


def parse_config(path: Path) -> WorkerAgentConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile_path = payload.get("profile_path")
    return WorkerAgentConfig(
        endpoint=payload["endpoint"],
        worker_id=payload["worker_id"],
        roles=list(payload["roles"]),
        controller_version=payload["controller_version"],
        dispatch_priority=int(payload.get("dispatch_priority", 100)),
        heartbeat_ttl_seconds=int(payload.get("heartbeat_ttl_seconds", 120)),
        heartbeat_interval_seconds=float(payload.get("heartbeat_interval_seconds", 30)),
        poll_interval_seconds=float(payload.get("poll_interval_seconds", 2)),
        lease_seconds=int(payload.get("lease_seconds", 120)),
        profile_path=Path(profile_path) if profile_path else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--correlation-id", default="worker-agent-once")
    args = parser.parse_args()

    agent = WorkerAgent(parse_config(Path(args.config)))
    if args.once:
        print(
            json.dumps(
                agent.run_once(args.correlation_id),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return
    agent.run_forever()


if __name__ == "__main__":
    main()
