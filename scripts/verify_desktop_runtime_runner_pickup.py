#!/usr/bin/env python3
"""E2E governado do runner dedicado desktop-pc24x7-runtime."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

TARGET_REPOSITORY = "ericson-j-santos/desktop-pc24x7-runtime"
TARGET_SHA = "4f71186f3c7636ad80f8bd14c74e3fded28101ec"
TARGET_WORKFLOW = "desktop-rdc-recovery.yml"
CONFIRM = "VERIFY-DESKTOP-RUNTIME-RUNNER-PICKUP"
API_ROOT = "https://api.github.com"
JsonRequester = Callable[[urllib.request.Request], dict[str, Any]]
StatusSender = Callable[[urllib.request.Request], int]


class PickupError(RuntimeError):
    pass


def api_request(
    token: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> urllib.request.Request:
    data = None if body is None else json.dumps(body).encode("utf-8")
    return urllib.request.Request(
        API_ROOT + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ReqSys-Desktop-Runtime-Pickup-E2E/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )


def request_json(request: urllib.request.Request) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise PickupError("github_response_invalid")
    return payload


def send_status(request: urllib.request.Request) -> int:
    with urllib.request.urlopen(request, timeout=30) as response:
        return int(response.status)


def current_main_sha(token: str, requester: JsonRequester = request_json) -> str:
    payload = requester(api_request(token, f"/repos/{TARGET_REPOSITORY}/commits/main"))
    sha = str(payload.get("sha") or "").lower()
    if len(sha) != 40:
        raise PickupError("target_main_sha_invalid")
    return sha


def workflow_runs(token: str, requester: JsonRequester = request_json) -> list[dict[str, Any]]:
    payload = requester(
        api_request(
            token,
            f"/repos/{TARGET_REPOSITORY}/actions/workflows/{TARGET_WORKFLOW}/runs"
            "?event=workflow_dispatch&per_page=30",
        )
    )
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise PickupError("workflow_runs_invalid")
    return [item for item in runs if isinstance(item, dict)]


def dispatch(token: str, sender: StatusSender = send_status) -> None:
    status = sender(
        api_request(
            token,
            f"/repos/{TARGET_REPOSITORY}/actions/workflows/{TARGET_WORKFLOW}/dispatches",
            method="POST",
            body={"ref": "main"},
        )
    )
    if status not in {200, 201, 202, 204}:
        raise PickupError(f"workflow_dispatch_failed:{status}")


def find_new_run(
    runs: list[dict[str, Any]],
    *,
    before_ids: set[int],
) -> dict[str, Any] | None:
    candidates = []
    for item in runs:
        try:
            run_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if run_id <= 0 or run_id in before_ids:
            continue
        if str(item.get("event") or "") != "workflow_dispatch":
            continue
        if str(item.get("head_sha") or "").lower() != TARGET_SHA:
            continue
        candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda item: int(item.get("id") or 0))


def verify_pickup(
    token: str,
    *,
    requester: JsonRequester = request_json,
    sender: StatusSender = send_status,
    timeout_seconds: float = 240.0,
    poll_seconds: float = 3.0,
) -> dict[str, Any]:
    observed_main = current_main_sha(token, requester)
    if observed_main != TARGET_SHA:
        raise PickupError("target_main_sha_mismatch")

    before = workflow_runs(token, requester)
    before_ids = {
        int(item["id"])
        for item in before
        if isinstance(item.get("id"), int)
    }
    dispatch(token, sender)

    deadline = time.monotonic() + timeout_seconds
    selected: dict[str, Any] | None = None
    last_status = "not_found"
    while time.monotonic() < deadline:
        runs = workflow_runs(token, requester)
        if selected is None:
            selected = find_new_run(runs, before_ids=before_ids)
        else:
            selected_id = int(selected.get("id") or 0)
            selected = next(
                (item for item in runs if int(item.get("id") or 0) == selected_id),
                selected,
            )
        if selected is None:
            time.sleep(poll_seconds)
            continue

        last_status = str(selected.get("status") or "unknown").casefold()
        if last_status == "completed":
            conclusion = str(selected.get("conclusion") or "unknown").casefold()
            if conclusion != "success":
                raise PickupError(f"target_workflow_failed:{conclusion}")
            return {
                "ok": True,
                "state": "target_runner_pickup_e2e_passed",
                "target_repository": TARGET_REPOSITORY,
                "target_sha": TARGET_SHA,
                "workflow": TARGET_WORKFLOW,
                "run_id": int(selected.get("id") or 0),
                "run_url": str(selected.get("html_url") or ""),
                "status": last_status,
                "conclusion": conclusion,
                "production_touched": False,
                "reboot_performed": False,
                "secret_logged": False,
            }
        time.sleep(poll_seconds)

    raise PickupError(f"target_workflow_timeout:{last_status}")


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        write_evidence(args.evidence_file, {"ok": False, "state": "confirmation_invalid"})
        return 2

    token = os.environ.get("GH_TOKEN") or ""
    if not token:
        write_evidence(args.evidence_file, {"ok": False, "state": "github_admin_token_missing"})
        return 2

    try:
        result = verify_pickup(token, timeout_seconds=args.timeout_seconds)
    except (PickupError, urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as exc:
        result = {
            "ok": False,
            "state": str(exc)[:200] if isinstance(exc, PickupError) else "pickup_e2e_failed",
            "error_type": type(exc).__name__,
            "target_repository": TARGET_REPOSITORY,
            "target_sha": TARGET_SHA,
            "workflow": TARGET_WORKFLOW,
            "production_touched": False,
            "reboot_performed": False,
            "secret_logged": False,
        }

    write_evidence(args.evidence_file, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
