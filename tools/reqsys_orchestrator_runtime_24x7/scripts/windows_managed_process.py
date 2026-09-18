from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from ctypes import wintypes
from datetime import datetime
from pathlib import Path


TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def iso_epoch(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.timestamp()


def filetime_epoch(value: wintypes.FILETIME) -> float:
    ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
    return ticks / 10_000_000 - 11_644_473_600


def require_windows():
    if os.name != "nt":
        raise RuntimeError("Windows is required")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def snapshot_processes(kernel32) -> dict[int, tuple[int, str]]:
    handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    result: dict[int, tuple[int, str]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(handle, ctypes.byref(entry))
        while ok:
            result[int(entry.th32ProcessID)] = (
                int(entry.th32ParentProcessID),
                entry.szExeFile,
            )
            ok = kernel32.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(handle)
    return result


def query_process(kernel32, pid: int) -> tuple[str, float, int]:
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE,
        False,
        pid,
    )
    if not handle:
        raise ProcessLookupError(pid)
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            raise OSError(ctypes.get_last_error(), "QueryFullProcessImageNameW failed")
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
        return buffer.value, filetime_epoch(creation), handle
    except Exception:
        kernel32.CloseHandle(handle)
        raise


def descendants(processes: dict[int, tuple[int, str]], root_pid: int) -> list[int]:
    children: dict[int, list[int]] = {}
    for pid, (ppid, _) in processes.items():
        children.setdefault(ppid, []).append(pid)
    ordered: list[int] = []

    def visit(pid: int) -> None:
        for child in children.get(pid, []):
            visit(child)
        ordered.append(pid)

    visit(root_pid)
    return ordered


def terminate_managed_tree(
    pid: int,
    *,
    expected_start_after: float,
    expected_start_before: float,
) -> dict:
    kernel32 = require_windows()
    image, created_at, root_handle = query_process(kernel32, pid)
    kernel32.CloseHandle(root_handle)

    basename = Path(image).name.lower()
    if not basename.startswith("python"):
        raise RuntimeError(f"refusing non-Python root process: {basename}")
    if not expected_start_after <= created_at <= expected_start_before:
        raise RuntimeError(
            f"root creation time outside approved window: {created_at}"
        )

    processes = snapshot_processes(kernel32)
    if pid not in processes:
        raise ProcessLookupError(pid)

    terminated: list[dict] = []
    for target_pid in descendants(processes, pid):
        try:
            target_image, _, handle = query_process(kernel32, target_pid)
        except ProcessLookupError:
            continue
        try:
            if not kernel32.TerminateProcess(handle, 0):
                raise OSError(ctypes.get_last_error(), "TerminateProcess failed")
            kernel32.WaitForSingleObject(handle, 5000)
            terminated.append(
                {"pid": target_pid, "image": Path(target_image).name}
            )
        finally:
            kernel32.CloseHandle(handle)
    return {
        "ok": True,
        "root_pid": pid,
        "root_image": basename,
        "created_at_epoch": created_at,
        "terminated": terminated,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-start-after", required=True)
    parser.add_argument("--expected-start-before", required=True)
    args = parser.parse_args()

    if args.pid <= 0 or args.pid == os.getpid():
        raise SystemExit("invalid pid")
    result = terminate_managed_tree(
        args.pid,
        expected_start_after=iso_epoch(args.expected_start_after),
        expected_start_before=iso_epoch(args.expected_start_before),
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
