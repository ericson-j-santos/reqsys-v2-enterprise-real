#!/usr/bin/env python3
"""Collect bounded Windows virtualization/Linux capability metadata without launching WSL."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import socket
import sys
from typing import Callable

SHA40 = re.compile(r"^[0-9a-f]{40}$")
HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
PF_NX_ENABLED = 12
PF_SECOND_LEVEL_ADDRESS_TRANSLATION = 20
PF_VIRT_FIRMWARE_ENABLED = 21
CONTRACT_ERRORS = {"expected_host_invalid", "requested_source_sha_invalid", "host_mismatch", "windows_required"}


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


def _safe_windows_metadata(get_version=None) -> dict:
    provider = get_version or getattr(sys, "getwindowsversion", None)
    if provider is None:
        return {"os": "Windows"}
    try:
        version = provider()
        release = f"{int(version.major)}.{int(version.minor)}.{int(version.build)}"
    except (AttributeError, OSError, TypeError, ValueError):
        return {"os": "Windows"}
    return {"os": "Windows", "os_release": release}


def _wsl_result(status: str, count: int | None, reason: str) -> dict:
    return {
        "status": status,
        "count": count,
        "reason": reason,
        "scope": "current_executor_hkcu",
        "host_wide": False,
        "names_collected": False,
    }


def registered_wsl_distribution_count(opener=None, query_info=None) -> dict:
    if os.name != "nt" and opener is None:
        return _wsl_result("unavailable", None, "windows_required")
    if opener is None:
        try:
            import winreg
        except ImportError:
            return _wsl_result("unavailable", None, "registry_api_unavailable")

        def opener():
            return winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Lxss",
                0,
                winreg.KEY_READ,
            )

    try:
        key = opener()
    except FileNotFoundError:
        return _wsl_result("measured", 0, "registry_key_absent")
    except PermissionError:
        return _wsl_result("unknown", None, "registry_access_denied")
    except OSError:
        return _wsl_result("unknown", None, "registry_open_failed")
    except (ImportError, ValueError):
        return _wsl_result("unknown", None, "registry_open_invalid")

    try:
        if query_info is None:
            try:
                import winreg
            except ImportError:
                return _wsl_result("unavailable", None, "registry_api_unavailable")
            query_info = winreg.QueryInfoKey
        try:
            count = int(query_info(key)[0])
        except PermissionError:
            return _wsl_result("unknown", None, "registry_access_denied")
        except ValueError:
            return _wsl_result("unknown", None, "registry_data_invalid")
        except (OSError, TypeError, IndexError):
            return _wsl_result("unknown", None, "registry_query_failed")
        return _wsl_result("measured", count, "registry_query_succeeded")
    finally:
        close = getattr(key, "Close", None)
        if close:
            close()


def collect(
    *,
    expected_host: str,
    requested_source_sha: str,
    feature_checker=None,
    wsl_opener=None,
    wsl_query_info=None,
    windows_version_provider=None,
    windows_identity=None,
) -> dict:
    if not HOST.fullmatch(expected_host):
        raise ValueError("expected_host_invalid")
    if not SHA40.fullmatch(requested_source_sha):
        raise ValueError("requested_source_sha_invalid")
    observed = socket.gethostname().strip()
    if observed.casefold() != expected_host.casefold():
        raise ValueError("host_mismatch")
    on_windows = (
        bool(windows_identity())
        if windows_identity is not None
        else os.name == "nt" and sys.platform == "win32"
    )
    if not on_windows:
        raise ValueError("windows_required")
    virtualization = windows_processor_features(feature_checker)
    wsl = registered_wsl_distribution_count(wsl_opener, wsl_query_info)
    result = {
        "schema_version": "1.1.0",
        "status": "diagnostic_collected",
        "host": observed,
        "requested_source_sha": requested_source_sha,
        "observed_source_sha": None,
        "source_verified": False,
        "source_provenance": "requested_only",
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
        "decision_reason": "requires_authorized_source_and_linux_runtime_proof",
    }
    result.update(_safe_windows_metadata(windows_version_provider))
    return result


def _safe_error_code(exc: ValueError) -> str:
    code = str(exc)
    return code if code in CONTRACT_ERRORS else "contract_validation_failed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--requested-source-sha", required=True)
    args = parser.parse_args()
    try:
        result = collect(
            expected_host=args.expected_host,
            requested_source_sha=args.requested_source_sha,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "reason": _safe_error_code(exc)}))
        return 2
    except OSError:
        print(json.dumps({"status": "blocked", "reason": "unexpected_os_error"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
