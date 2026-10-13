#!/usr/bin/env python3
"""Collect bounded Windows virtualization/Linux capability metadata without launching WSL."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
import socket
from typing import Callable

SHA40 = re.compile(r"^[0-9a-f]{40}$")
HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
PF_NX_ENABLED = 12
PF_SECOND_LEVEL_ADDRESS_TRANSLATION = 20
PF_VIRT_FIRMWARE_ENABLED = 21


def windows_processor_features(checker: Callable[[int], bool] | None = None) -> dict:
    if checker is None:
        if os.name != "nt":
            return {"status": "unavailable", "reason": "windows_required"}
        try:
            api = ctypes.WinDLL("kernel32", use_last_error=True)

            def checker(feature: int) -> bool:
                return bool(api.IsProcessorFeaturePresent(feature))
        except (OSError, AttributeError):
            return {"status": "unavailable", "reason": "windows_api_unavailable"}
    return {
        "status": "measured",
        "nx_enabled": checker(PF_NX_ENABLED),
        "second_level_address_translation": checker(PF_SECOND_LEVEL_ADDRESS_TRANSLATION),
        "virtualization_firmware_enabled": checker(PF_VIRT_FIRMWARE_ENABLED),
    }


def registered_wsl_distribution_count(opener=None, query_info=None) -> dict:
    if os.name != "nt" and opener is None:
        return {"status": "unavailable", "count": None, "names_collected": False}
    try:
        if opener is None:
            import winreg

            def opener():
                return winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Lxss",
                    0,
                    winreg.KEY_READ,
                )
        key = opener()
        try:
            if query_info is None:
                import winreg
                query_info = winreg.QueryInfoKey
            count = int(query_info(key)[0])
        finally:
            close = getattr(key, "Close", None)
            if close:
                close()
        return {"status": "measured", "count": count, "names_collected": False}
    except (OSError, ImportError, ValueError):
        return {"status": "measured", "count": 0, "names_collected": False}


def collect(*, expected_host: str, source_sha: str, feature_checker=None, wsl_opener=None, wsl_query_info=None) -> dict:
    if not HOST.fullmatch(expected_host):
        raise ValueError("expected_host_invalid")
    if not SHA40.fullmatch(source_sha):
        raise ValueError("source_sha_invalid")
    observed = socket.gethostname().strip()
    if observed.casefold() != expected_host.casefold():
        raise ValueError("host_mismatch")
    if platform.system() != "Windows":
        raise ValueError("windows_required")
    virtualization = windows_processor_features(feature_checker)
    wsl = registered_wsl_distribution_count(wsl_opener, wsl_query_info)
    return {
        "schema_version": "1.0.0",
        "status": "diagnostic_collected",
        "host": observed,
        "source_sha": source_sha,
        "os": "Windows",
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "virtualization": virtualization,
        "wsl": wsl,
        "linux_kernel_executed": False,
        "wsl_executed": False,
        "systemd_verified": False,
        "systemd_status": "unknown",
        "boot_modified": False,
        "windows_features_modified": False,
        "services_modified": False,
        "secrets_read": False,
        "ready_for_linux_pilot": False,
        "decision_reason": "requires_authorized_non_mutating_wsl_and_systemd_proof",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = collect(expected_host=args.expected_host, source_sha=args.source_sha)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
