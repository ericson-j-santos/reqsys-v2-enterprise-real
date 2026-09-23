#!/usr/bin/env python3
"""E2E governado do runner dedicado usando somente a autenticação local do GitHub CLI."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

TARGET_REPOSITORY = "ericson-j-santos/desktop-pc24x7-runtime"
TARGET_SHA = "4f71186f3c7636ad80f8bd14c74e3fded28101ec"
TARGET_WORKFLOW = "desktop-rdc-recovery.yml"
EXPECTED_GITHUB_LOGIN = "ericson-j-santos"
CONFIRM = "VERIFY-DESKTOP-RUNTIME-RUNNER-PICKUP"
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class PickupError(RuntimeError):
    pass


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def find_gh() -> Path:
    located = shutil.which("gh")
    candidates = [
        Path(located) if located else None,
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "GitHub CLI" / "gh.exe",
    ]
    for item in candidates:
        if item is not None and item.is_file():
            return item
    raise PickupError("github_cli_required")


def run_gh(gh: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(gh), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=gh_env(),
    )


def ensure_local_auth(gh: Path, runner: Runner | None = None) -> None:
    invoke = runner or (lambda args: run_gh(gh, args))
    status = invoke(["auth", "status", "--hostname", "github.com"])
    if status.returncode != 0:
        raise PickupError("github_auth_required")
    who = invoke(["api", "user", "--jq", ".login"])
    login = who.stdout.strip() if who.returncode == 0 else ""
    if login.casefold() != EXPECTED_GITHUB_LOGIN.casefold():
        raise PickupError("github_account_mismatch")


def gh_json(gh: Path, args: list[str], runner: Runner | None = None) -> dict[str, Any]:
    invoke = runner or (lambda argv: run_gh(gh, argv))
    cp = invoke(args)
    if cp.returncode != 0:
        raise PickupError("github_api_failed")
    try:
        payload = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise PickupError("github_response_invalid") from exc
    if not isinstance(payload, dict):
        raise PickupError("github_response_invalid")
    return payload


def current_main_sha(gh: Path, runner: Runner | None = None) -> str:
    payload = gh_json(gh, ["api", f"repos/{TARGET_REPOSITORY}/commits/main"], runner)
    sha = str(payload.get("sha") or "").lower()
    if len(sha) != 40:
        raise PickupError("target_main_sha_invalid")
    return sha


def workflow_runs(gh: Path, runner: Runner | None = None) -> list[dict[str, Any]]:
    payload = gh_json(
        gh,
        [
            "api",
            f"repos/{TARGET_REPOSITORY}/actions/workflows/{TARGET_WORKFLOW}/runs"
            "?event=workflow_dispatch&per_page=30",
        ],
        runner,
    )
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise PickupError("workflow_runs_invalid")
    return [item for item in runs if isinstance(item, dict)]


def dispatch(gh: Path, runner: Runner | None = None) -> None:
    invoke = runner or (lambda args: run_gh(gh, args))
    cp = invoke(
        [
            "api",
            "--method",
            "POST",
            f"repos/{TARGET_REPOSITORY}/actions/workflows/{TARGET_WORKFLOW}/dispatches",
            "-f",
            "ref=main",
        ]
    )
    if cp.returncode != 0:
        raise PickupError("workflow_dispatch_failed")


def find_new_run(runs: list[dict[str, Any]], *, before_ids: set[int]) -> dict[str, Any] | None:
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
    gh: Path,
    *,
    runner: Runner | None = None,
    timeout_seconds: float = 240.0,
    poll_seconds: float = 3.0,
) -> dict[str, Any]:
    ensure_local_auth(gh, runner)
    observed_main = current_main_sha(gh, runner)
    if observed_main != TARGET_SHA:
        raise PickupError("target_main_sha_mismatch")

    before = workflow_runs(gh, runner)
    before_ids = {int(item["id"]) for item in before if isinstance(item.get("id"), int)}
    dispatch(gh, runner)

    deadline = time.monotonic() + timeout_seconds
    selected: dict[str, Any] | None = None
    last_status = "not_found"
    while time.monotonic() < deadline:
        runs = workflow_runs(gh, runner)
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
                "auth_source": "local_gh",
                "production_touched": False,
                "reboot_performed": False,
                "secret_logged": False,
            }
        time.sleep(poll_seconds)

    raise PickupError(f"target_workflow_timeout:{last_status}")


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        write_evidence(args.evidence_file, {"ok": False, "state": "confirmation_invalid"})
        return 2

    try:
        gh = find_gh()
        result = verify_pickup(gh, timeout_seconds=args.timeout_seconds)
    except (PickupError, OSError, subprocess.SubprocessError) as exc:
        result = {
            "ok": False,
            "state": str(exc)[:200] if isinstance(exc, PickupError) else "pickup_e2e_failed",
            "error_type": type(exc).__name__,
            "target_repository": TARGET_REPOSITORY,
            "target_sha": TARGET_SHA,
            "workflow": TARGET_WORKFLOW,
            "auth_source": "local_gh",
            "production_touched": False,
            "reboot_performed": False,
            "secret_logged": False,
        }

    write_evidence(args.evidence_file, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
