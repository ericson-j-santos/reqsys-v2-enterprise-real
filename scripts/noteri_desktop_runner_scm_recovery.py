from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
SCM_MACHINE = r"\\\\DESKTOP-PDQK954"
CONFIRM = "RECOVER-NOTERI-DESKTOP-RUNNER-SCM"
RUNNER_MARKERS = ("actions.runner", "github actions runner")

SC_MANAGER_CONNECT = 0x0001
SC_MANAGER_ENUMERATE_SERVICE = 0x0004
SERVICE_QUERY_STATUS = 0x0004
SERVICE_START = 0x0010
SERVICE_WIN32 = 0x00000030
SERVICE_STATE_ALL = 0x00000003
SC_ENUM_PROCESS_INFO = 0
SC_STATUS_PROCESS_INFO = 0
SERVICE_STOPPED = 1
SERVICE_START_PENDING = 2
SERVICE_STOP_PENDING = 3
SERVICE_RUNNING = 4
SERVICE_CONTINUE_PENDING = 5
SERVICE_PAUSE_PENDING = 6
SERVICE_PAUSED = 7
ERROR_ACCESS_DENIED = 5
ERROR_MORE_DATA = 234
ERROR_SERVICE_ALREADY_RUNNING = 1056

STATE_NAMES = {
    SERVICE_STOPPED: "stopped",
    SERVICE_START_PENDING: "start_pending",
    SERVICE_STOP_PENDING: "stop_pending",
    SERVICE_RUNNING: "running",
    SERVICE_CONTINUE_PENDING: "continue_pending",
    SERVICE_PAUSE_PENDING: "pause_pending",
    SERVICE_PAUSED: "paused",
}


class RecoveryError(RuntimeError):
    def __init__(self, code: str, *, winerror: int | None = None):
        super().__init__(code)
        self.code = code
        self.winerror = winerror


class SERVICE_STATUS_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwServiceFlags", wintypes.DWORD),
    ]


class ENUM_SERVICE_STATUS_PROCESSW(ctypes.Structure):
    _fields_ = [
        ("lpServiceName", wintypes.LPWSTR),
        ("lpDisplayName", wintypes.LPWSTR),
        ("ServiceStatusProcess", SERVICE_STATUS_PROCESS),
    ]


class Backend(Protocol):
    def runner_candidates(self) -> list[dict[str, object]]: ...
    def ensure_running(self, service_name: str, timeout_seconds: float) -> dict[str, object]: ...


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_request(confirm: str, correlation_id: str) -> None:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    correlation = str(correlation_id or "").strip()
    if len(correlation) < 8 or len(correlation) > 200:
        raise RecoveryError("correlation_id_invalid")


def validate_host() -> str:
    if os.name != "nt":
        raise RecoveryError("platform_not_windows")
    source = socket.gethostname()
    if source.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")
    return source


class WindowsScmBackend:
    def __init__(self) -> None:
        if os.name != "nt":
            raise RecoveryError("platform_not_windows")
        self.api = ctypes.WinDLL("advapi32", use_last_error=True)
        self.api.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        self.api.OpenSCManagerW.restype = wintypes.HANDLE
        self.api.EnumServicesStatusExW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.BYTE),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPCWSTR,
        ]
        self.api.EnumServicesStatusExW.restype = wintypes.BOOL
        self.api.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
        self.api.OpenServiceW.restype = wintypes.HANDLE
        self.api.QueryServiceStatusEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.BYTE),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.api.QueryServiceStatusEx.restype = wintypes.BOOL
        self.api.StartServiceW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPCWSTR),
        ]
        self.api.StartServiceW.restype = wintypes.BOOL
        self.api.CloseServiceHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseServiceHandle.restype = wintypes.BOOL

    @staticmethod
    def _raise_last(code: str) -> None:
        err = ctypes.get_last_error()
        if err == ERROR_ACCESS_DENIED:
            raise RecoveryError("scm_access_denied", winerror=err)
        raise RecoveryError(code, winerror=err)

    def _open_manager(self, access: int):
        handle = self.api.OpenSCManagerW(SCM_MACHINE, None, access)
        if not handle:
            self._raise_last("scm_open_failed")
        return handle

    def runner_candidates(self) -> list[dict[str, object]]:
        manager = self._open_manager(SC_MANAGER_CONNECT | SC_MANAGER_ENUMERATE_SERVICE)
        try:
            needed = wintypes.DWORD(0)
            returned = wintypes.DWORD(0)
            resume = wintypes.DWORD(0)
            ok = self.api.EnumServicesStatusExW(
                manager,
                SC_ENUM_PROCESS_INFO,
                SERVICE_WIN32,
                SERVICE_STATE_ALL,
                None,
                0,
                ctypes.byref(needed),
                ctypes.byref(returned),
                ctypes.byref(resume),
                None,
            )
            if not ok:
                err = ctypes.get_last_error()
                if err != ERROR_MORE_DATA:
                    if err == ERROR_ACCESS_DENIED:
                        raise RecoveryError("scm_access_denied", winerror=err)
                    raise RecoveryError("scm_enumeration_failed", winerror=err)
            if needed.value <= 0:
                return []

            raw = (wintypes.BYTE * needed.value)()
            resume = wintypes.DWORD(0)
            ok = self.api.EnumServicesStatusExW(
                manager,
                SC_ENUM_PROCESS_INFO,
                SERVICE_WIN32,
                SERVICE_STATE_ALL,
                raw,
                needed.value,
                ctypes.byref(needed),
                ctypes.byref(returned),
                ctypes.byref(resume),
                None,
            )
            if not ok:
                self._raise_last("scm_enumeration_failed")

            entries = ctypes.cast(
                raw,
                ctypes.POINTER(ENUM_SERVICE_STATUS_PROCESSW),
            )
            candidates: list[dict[str, object]] = []
            for index in range(returned.value):
                entry = entries[index]
                service_name = str(entry.lpServiceName or "").strip()
                display_name = str(entry.lpDisplayName or "").strip()
                haystack = f"{service_name} {display_name}".casefold()
                if not any(marker in haystack for marker in RUNNER_MARKERS):
                    continue
                candidates.append(
                    {
                        "service_name": service_name,
                        "display_name": display_name,
                        "state": STATE_NAMES.get(
                            int(entry.ServiceStatusProcess.dwCurrentState),
                            "unknown",
                        ),
                    }
                )
            return candidates
        finally:
            self.api.CloseServiceHandle(manager)

    def _query_state(self, service) -> int:
        status = SERVICE_STATUS_PROCESS()
        needed = wintypes.DWORD(0)
        ok = self.api.QueryServiceStatusEx(
            service,
            SC_STATUS_PROCESS_INFO,
            ctypes.cast(ctypes.byref(status), ctypes.POINTER(wintypes.BYTE)),
            ctypes.sizeof(status),
            ctypes.byref(needed),
        )
        if not ok:
            self._raise_last("service_status_failed")
        return int(status.dwCurrentState)

    def ensure_running(self, service_name: str, timeout_seconds: float) -> dict[str, object]:
        manager = self._open_manager(SC_MANAGER_CONNECT)
        try:
            service = self.api.OpenServiceW(
                manager,
                service_name,
                SERVICE_QUERY_STATUS | SERVICE_START,
            )
            if not service:
                self._raise_last("service_open_failed")
            try:
                before = self._query_state(service)
                changed = False
                if before == SERVICE_STOPPED:
                    if not self.api.StartServiceW(service, 0, None):
                        err = ctypes.get_last_error()
                        if err != ERROR_SERVICE_ALREADY_RUNNING:
                            if err == ERROR_ACCESS_DENIED:
                                raise RecoveryError("service_start_access_denied", winerror=err)
                            raise RecoveryError("service_start_failed", winerror=err)
                    changed = True
                elif before not in {SERVICE_RUNNING, SERVICE_START_PENDING}:
                    raise RecoveryError(f"service_state_not_startable_{before}")

                deadline = time.monotonic() + timeout_seconds
                after = self._query_state(service)
                while after == SERVICE_START_PENDING and time.monotonic() < deadline:
                    time.sleep(0.5)
                    after = self._query_state(service)
                if after != SERVICE_RUNNING:
                    raise RecoveryError(f"service_not_running_{after}")
                return {
                    "before_state": STATE_NAMES.get(before, "unknown"),
                    "after_state": "running",
                    "changed": changed,
                }
            finally:
                self.api.CloseServiceHandle(service)
        finally:
            self.api.CloseServiceHandle(manager)


def recover(
    confirm: str,
    correlation_id: str,
    *,
    backend: Backend | None = None,
    source_host: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, object]:
    validate_request(confirm, correlation_id)
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise RecoveryError("timeout_invalid")
    source = source_host or validate_host()
    if source.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")

    scm = backend or WindowsScmBackend()
    candidates = scm.runner_candidates()
    if len(candidates) == 0:
        raise RecoveryError("runner_service_not_found")
    if len(candidates) != 1:
        raise RecoveryError("runner_service_ambiguous")

    candidate = candidates[0]
    service_name = str(candidate.get("service_name") or "").strip()
    if not service_name:
        raise RecoveryError("runner_service_name_invalid")

    result = scm.ensure_running(service_name, timeout_seconds)
    return {
        "ok": True,
        "environment": "DEV",
        "source_host": source,
        "target_host": TARGET_HOST,
        "transport": "windows_scm_rpc",
        "target_match_count": 1,
        "service_name": service_name,
        "service_display_name": str(candidate.get("display_name") or "").strip(),
        "discovered_state": str(candidate.get("state") or "unknown"),
        "before_state": result["before_state"],
        "after_state": result["after_state"],
        "changed": bool(result["changed"]),
        "correlation_id": correlation_id,
        "observed_at": utc_iso(),
        "production_touched": False,
        "secrets_read": False,
        "rdc_required": False,
        "remote_shell_used": False,
    }


def blocked_payload(exc: RecoveryError, correlation_id: str) -> dict[str, object]:
    return {
        "ok": False,
        "environment": "DEV",
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "transport": "windows_scm_rpc",
        "error_code": exc.code,
        "winerror": exc.winerror,
        "correlation_id": correlation_id,
        "observed_at": utc_iso(),
        "production_touched": False,
        "secrets_read": False,
        "rdc_required": False,
        "remote_shell_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    try:
        payload = recover(
            args.confirm,
            args.correlation_id,
            timeout_seconds=args.timeout_seconds,
        )
        exit_code = 0
    except RecoveryError as exc:
        payload = blocked_payload(exc, args.correlation_id)
        exit_code = 2

    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
