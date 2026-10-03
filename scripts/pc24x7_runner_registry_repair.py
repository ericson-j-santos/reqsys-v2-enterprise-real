#!/usr/bin/env python3
"""Probe/repair governado do registro do runner PC24x7 via GitHub REST."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
EXPECTED_RUNNER = "DESKTOP-PDQK954"
REQUIRED_LABELS = ("self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev")
CUSTOM_LABELS = ("pc24x7", "reqsys-dev")
CONFIRM = "REPAIR-PC24X7-RUNNER-REGISTRY"
API_ROOT = "https://api.github.com"
Requester = Callable[[urllib.request.Request], dict[str, Any]]


class RegistryRepairError(RuntimeError):
    pass


def default_request(request: urllib.request.Request) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RegistryRepairError("github_response_invalid")
    return payload


def _request(token: str, path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> urllib.request.Request:
    data = None if body is None else json.dumps(body).encode("utf-8")
    return urllib.request.Request(
        API_ROOT + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ReqSys-PC24x7-Runner-Registry-Repair/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )


def _labels(item: dict[str, Any]) -> list[str]:
    raw = item.get("labels")
    if not isinstance(raw, list):
        return []
    return sorted({
        str(label.get("name") or "")
        for label in raw
        if isinstance(label, dict) and str(label.get("name") or "")
    })


def snapshot(token: str, requester: Requester = default_request) -> dict[str, Any]:
    payload = requester(_request(token, f"/repos/{REPOSITORY}/actions/runners?per_page=100"))
    runners = payload.get("runners")
    if not isinstance(runners, list):
        raise RegistryRepairError("runner_registry_invalid")
    matches = [
        item for item in runners
        if isinstance(item, dict)
        and str(item.get("name") or "").casefold() == EXPECTED_RUNNER.casefold()
    ]
    if not matches:
        return {"present": False, "status": "missing", "busy": False, "labels": [], "runner_id": None}
    if len(matches) != 1:
        raise RegistryRepairError("runner_registry_ambiguous")
    item = matches[0]
    runner_id = item.get("id")
    if not isinstance(runner_id, int) or runner_id <= 0:
        raise RegistryRepairError("runner_id_invalid")
    return {
        "present": True,
        "status": str(item.get("status") or "unknown").casefold(),
        "busy": bool(item.get("busy")),
        "labels": _labels(item),
        "runner_id": runner_id,
    }


def labels_ok(labels: list[str]) -> bool:
    observed = {value.casefold() for value in labels}
    return {value.casefold() for value in REQUIRED_LABELS}.issubset(observed)


def custom_labels_ok(labels: list[str]) -> bool:
    observed = {value.casefold() for value in labels}
    return {value.casefold() for value in CUSTOM_LABELS}.issubset(observed)


def repair(token: str, requester: Requester = default_request) -> dict[str, Any]:
    before = snapshot(token, requester)
    if not before["present"]:
        return {"ok": False, "state": "runner_missing", "before": before, "after": before, "mutated": False}
    if before["status"] != "online":
        return {"ok": False, "state": "runner_offline", "before": before, "after": before, "mutated": False}

    mutated = False
    if not custom_labels_ok(before["labels"]):
        requester(_request(
            token,
            f"/repos/{REPOSITORY}/actions/runners/{before['runner_id']}/labels",
            method="PUT",
            body={"labels": list(CUSTOM_LABELS)},
        ))
        mutated = True

    after = snapshot(token, requester)
    if after["status"] != "online":
        return {"ok": False, "state": "runner_became_offline", "before": before, "after": after, "mutated": mutated}
    if not labels_ok(after["labels"]):
        return {"ok": False, "state": "runner_labels_mismatch", "before": before, "after": after, "mutated": mutated}
    return {"ok": True, "state": "runner_registry_ready", "before": before, "after": after, "mutated": mutated}


def write_evidence(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        "schema_version": "1",
        "ok": bool(result.get("ok")),
        "state": result.get("state"),
        "runner_name": EXPECTED_RUNNER,
        "repository": REPOSITORY,
        "before": result.get("before"),
        "after": result.get("after"),
        "mutated": bool(result.get("mutated")),
        "custom_labels_target": list(CUSTOM_LABELS),
        "production_touched": False,
        "reboot_performed": False,
        "desktop_shell_executed": False,
        "secret_logged": False,
    }
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        print(json.dumps({"ok": False, "state": "confirmation_invalid"}, sort_keys=True))
        return 2
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(json.dumps({"ok": False, "state": "github_token_missing"}, sort_keys=True))
        return 2

    try:
        result = repair(token)
    except (RegistryRepairError, urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        result = {
            "ok": False,
            "state": "runner_registry_probe_failed",
            "mutated": False,
        }
    write_evidence(args.evidence_file, result)
    printable = {k: v for k, v in result.items() if k != "runner_id"}
    print(json.dumps(printable, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
