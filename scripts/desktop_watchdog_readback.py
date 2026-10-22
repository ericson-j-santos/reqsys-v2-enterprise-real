#!/usr/bin/env python3
"""Bounded read-only metadata receipt for the existing Desktop watchdog.

No credentials/configuration are read. This is not a recovery command and does
not attest the ReqSys producer, installed release, or continuous execution.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import io
import json
import locale
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import unicodedata
import xml.etree.ElementTree as ET

EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
TASK_NAME = r"\Automation\ReqSysDesktopControlPlaneWatchdog"
WATCHDOG_SERVICE = "reqsys-desktop-control-plane-watchdog"
EXPECTED_RUNNER_SERVICE = (
    "actions.runner.ericson-j-santos-reqsys-v2-enterprise-real.DESKTOP-PDQK954"
)
RECEIPT_REL = Path("artifacts/desktop-watchdog-readback/evidence.json")
RDC_RETIREMENT_MARKER = "EXTERNAL_RDC_RETIRED_FAIL_CLOSED_20261003"
MAX_STATE_BYTES = 65536
SHA_RE = re.compile(r"[0-9a-f]{40}")
CORRELATION_RE = re.compile(r"desktop-watchdog-readback-[0-9]+-[0-9]+")
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


class ReadbackError(RuntimeError):
    """Only fixed error codes may cross the evidence boundary."""


def require_identity(expected_sha: str, correlation_id: str) -> None:
    if os.name != "nt" or socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise ReadbackError("host_identity_mismatch")
    if os.environ.get("RUNNER_NAME", "").casefold() != EXPECTED_HOST.casefold():
        raise ReadbackError("runner_identity_mismatch")
    if os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        raise ReadbackError("repository_identity_mismatch")
    if not SHA_RE.fullmatch(expected_sha) or os.environ.get("GITHUB_SHA") != expected_sha:
        raise ReadbackError("sha_identity_mismatch")
    if not CORRELATION_RE.fullmatch(correlation_id):
        raise ReadbackError("correlation_identity_mismatch")


def _query_task(*suffix: str) -> subprocess.CompletedProcess[str]:
    # Fixed local task and executable; no shell, remote host or mutation verb.
    return subprocess.run(
        [r"C:\Windows\System32\schtasks.exe", "/Query", "/TN", TASK_NAME, *suffix],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=20,
        check=False,
        shell=False,
    )


def parse_task_xml(raw: str) -> dict:
    if len(raw) > MAX_STATE_BYTES or "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise ReadbackError("task_xml_invalid")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ReadbackError("task_xml_invalid") from exc
    if root.tag != "{http://schemas.microsoft.com/windows/2004/02/mit/task}Task":
        raise ReadbackError("task_xml_invalid")
    enabled = root.findtext("./t:Settings/t:Enabled", default="true", namespaces=NS)
    boot_enabled = any(
        node.findtext("t:Enabled", default="true", namespaces=NS).strip().casefold() == "true"
        for node in root.findall("./t:Triggers/t:BootTrigger", NS)
    )
    logon = root.findtext("./t:Principals/t:Principal/t:LogonType", default="", namespaces=NS)
    allowed_logon = {"S4U", "InteractiveToken", "Password", "ServiceAccount", "Group",
                     "InteractiveTokenOrPassword", "None"}
    return {
        "status": "observed",
        "exists": True,
        "enabled": enabled.strip().casefold() == "true",
        "trigger_at_startup": boot_enabled,
        "logon_type": logon if logon in allowed_logon else "unknown",
    }


def _header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if c.isalnum()).casefold()


def parse_last_result(raw: str) -> dict:
    if len(raw) > MAX_STATE_BYTES:
        return {"status": "unavailable", "reason": "task_csv_invalid"}
    rows = list(csv.DictReader(io.StringIO(raw)))
    if len(rows) != 1:
        return {"status": "unavailable", "reason": "task_csv_invalid"}
    row = {_header(str(key)): str(value or "").strip() for key, value in rows[0].items()}
    task = row.get("taskname") or row.get("nomedatarefa")
    value = row.get("lastresult") or row.get("ultimoresultado")
    if task != TASK_NAME or value is None or not re.fullmatch(r"(?:0[xX][0-9a-fA-F]{1,8}|-?[0-9]{1,10})", value):
        return {"status": "unavailable", "reason": "task_csv_fields_unverified"}
    number = int(value, 16 if value.lower().startswith("0x") else 10)
    if not -(2**31) <= number <= 2**32 - 1:
        return {"status": "unavailable", "reason": "task_result_out_of_range"}
    return {"status": "observed", "value": number, "successful_cycle_verified": False}


def task_metadata() -> dict:
    try:
        xml = _query_task("/XML")
        if xml.returncode != 0:
            return {"status": "unavailable", "reason": "task_query_failed", "exists": None}
        payload = parse_task_xml(xml.stdout)
        verbose = _query_task("/V", "/FO", "CSV")
        payload["last_task_result"] = (
            parse_last_result(verbose.stdout) if verbose.returncode == 0
            else {"status": "unavailable", "reason": "task_result_query_failed"}
        )
        return payload
    except (OSError, subprocess.SubprocessError, ReadbackError, csv.Error, ValueError):
        return {"status": "unavailable", "reason": "task_metadata_unavailable", "exists": None}


def runner_service_metadata() -> dict:
    """SCM connect + query-status only. Never read service config or accounts."""
    class ServiceStatusProcess(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in (
            "service_type", "current_state", "controls_accepted", "win32_exit_code",
            "service_specific_exit_code", "check_point", "wait_hint", "process_id", "flags"
        )]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenSCManagerW.restype = wintypes.HANDLE
    api.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenServiceW.restype = wintypes.HANDLE
    api.QueryServiceStatusEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.QueryServiceStatusEx.restype = wintypes.BOOL
    api.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    api.CloseServiceHandle.restype = wintypes.BOOL
    manager = api.OpenSCManagerW(None, None, 0x0001)  # SC_MANAGER_CONNECT
    if not manager:
        return {"status": "unavailable", "reason": "service_manager_query_denied"}
    service = None
    try:
        service = api.OpenServiceW(manager, EXPECTED_RUNNER_SERVICE, 0x0004)  # SERVICE_QUERY_STATUS
        if not service:
            if ctypes.get_last_error() == 1060:
                return {"status": "observed", "exists": False, "other_services_checked": False}
            return {"status": "unavailable", "reason": "service_query_denied"}
        state = ServiceStatusProcess()
        needed = wintypes.DWORD()
        if not api.QueryServiceStatusEx(service, 0, ctypes.byref(state), ctypes.sizeof(state), ctypes.byref(needed)):
            return {"status": "unavailable", "reason": "service_status_unavailable"}
        states = {1: "stopped", 2: "start_pending", 3: "stop_pending", 4: "running",
                  5: "continue_pending", 6: "pause_pending", 7: "paused"}
        return {
            "status": "observed", "exists": True,
            "state": states.get(state.current_state, "unknown"),
            "process_id": int(state.process_id),
            "other_services_checked": False,
            "github_connectivity_verified": False,
        }
    finally:
        if service:
            api.CloseServiceHandle(service)
        api.CloseServiceHandle(manager)


def _fixed_runtime_root() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not Path(local).is_absolute():
        raise ReadbackError("runtime_location_unavailable")
    return Path(local) / "ReqSys" / "DesktopControlPlaneWatchdog"


def _read_state(path: Path) -> dict:
    # Reject stable symlinks/junctions before reading only the fixed receipt.
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ReadbackError("state_reparse_blocked")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_STATE_BYTES:
        raise ReadbackError("state_file_invalid")
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if identity(before) != identity(opened):
            raise ReadbackError("state_changed_before_read")
        raw = handle.read(MAX_STATE_BYTES + 1)
        after = os.fstat(handle.fileno())
    if len(raw) > MAX_STATE_BYTES or identity(before) != identity(opened) or identity(opened) != identity(after):
        raise ReadbackError("state_changed_during_read")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ReadbackError("state_schema_invalid")
    return payload


def sanitize_state(payload: dict, observed_at: datetime) -> dict:
    if payload.get("host") != EXPECTED_HOST or payload.get("service") != WATCHDOG_SERVICE:
        return {"status": "unavailable", "reason": "state_identity_unverified"}
    sha = payload.get("source_sha")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        return {"status": "unavailable", "reason": "state_sha_unverified"}
    try:
        generated = datetime.fromisoformat(str(payload.get("generated_at", "")))
        if generated.tzinfo is None:
            raise ValueError
        age = (observed_at - generated).total_seconds()
        if age < -5:
            raise ValueError
    except (ValueError, OverflowError):
        return {"status": "unavailable", "reason": "state_timestamp_unverified"}
    runner = payload.get("github_runner")
    rdc = payload.get("rdc")
    runner = runner if isinstance(runner, dict) else {}
    rdc = rdc if isinstance(rdc, dict) else {}
    runner_status = runner.get("status")
    retired = (
        rdc.get("status") == "retired_fail_closed"
        and rdc.get("enabled") is False
        and rdc.get("recovered") is False
        and rdc.get("marker") == RDC_RETIREMENT_MARKER
    )
    return {
        "status": "observed",
        "service": WATCHDOG_SERVICE,
        "last_cycle_source_sha": sha,
        "last_cycle_generated_at": generated.astimezone(timezone.utc).isoformat(),
        "age_seconds": max(0, int(age)),
        "fresh_within_120_seconds": age <= 120,
        "runner_status": runner_status if isinstance(runner_status, str) and runner_status in {"process_running", "recovered", "failed"} else "unknown",
        "last_cycle_ok": payload.get("ok") if isinstance(payload.get("ok"), bool) else None,
        "rdc_retired_observed": retired,
        "installed_release_verified": False,
        "continuous_cycles_verified": False,
        "reqsys_producer_verified": False,
    }


def watchdog_state_metadata(observed_at: datetime) -> dict:
    try:
        payload = _read_state(_fixed_runtime_root() / "state.json")
        return sanitize_state(payload, observed_at)
    except FileNotFoundError:
        return {"status": "unavailable", "reason": "state_missing"}
    except (OSError, ValueError, ReadbackError, UnicodeError, RecursionError):
        return {"status": "unavailable", "reason": "state_unreadable_or_invalid"}


def collect(expected_sha: str, correlation_id: str) -> dict:
    require_identity(expected_sha, correlation_id)
    observed = datetime.now(timezone.utc)
    task = task_metadata()
    try:
        service = runner_service_metadata()
    except (OSError, AttributeError, ValueError):
        service = {"status": "unavailable", "reason": "service_metadata_unavailable"}
    state = watchdog_state_metadata(observed)
    complete = all(item.get("status") == "observed" for item in (task, service, state))
    complete = complete and task.get("last_task_result", {}).get("status") == "observed"
    return {
        "schema_version": "1",
        "result": "DESKTOP_WATCHDOG_READBACK_COLLECTED" if complete else "DESKTOP_WATCHDOG_READBACK_PARTIAL",
        "probe_ok": True,
        "collection_complete": complete,
        "host": EXPECTED_HOST, "runner_name": EXPECTED_HOST, "repository": EXPECTED_REPOSITORY,
        "sha": expected_sha, "correlation_id": correlation_id,
        "observed_at_utc": observed.isoformat(), "environment": "local-dev",
        "task_name": TASK_NAME, "task": task,
        "task_action_identity_verified": False,
        "runner_service_scope": "exact_name_probe",
        "runner_service_identity_verified": False,
        "runner_service_name_candidate": EXPECTED_RUNNER_SERVICE,
        "runner_service": service, "watchdog_last_state": state,
        "runtime_ready": False, "reqsys_producer_verified": False,
        "secrets_read": False, "private_config_read": False,
        "task_created_or_modified": False, "task_run_requested": False,
        "service_mutated": False, "production_touched": False,
        "remote_access_attempted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    try:
        receipt = collect(args.expected_sha, args.correlation_id)
    except (ReadbackError, OSError, ValueError):
        print(json.dumps({"result": "DESKTOP_WATCHDOG_READBACK_BLOCKED", "runtime_ready": False}))
        return 2
    path = Path(__file__).resolve().parents[1] / RECEIPT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0  # Partial metadata is an explicit diagnostic outcome, never readiness.


if __name__ == "__main__":
    raise SystemExit(main())
