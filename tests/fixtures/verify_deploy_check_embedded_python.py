#!/usr/bin/env python3
"""Validate the deploy-check contract under the pinned embeddable interpreter."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


def _load(path: Path, name: str) -> Any:
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_loader_unavailable")
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _emit(category: str) -> int:
    print(json.dumps({"ok": True, "category": category}, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=("probe-success", "probe-missing", "gateway-validation"),
    )
    parser.add_argument("--recovery-script", required=True, type=Path)
    parser.add_argument("--gateway-script", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--interpreter", type=Path)
    args = parser.parse_args()

    recovery = _load(args.recovery_script, "_reqsys_embedded_recovery")
    recovery.__package__ = None

    if args.mode == "probe-success":
        probe_error, run = recovery._load_identity_probe()
        if (
            probe_error.__name__ != "ProbeError"
            or run.__module__ != "_reqsys_fixed_pc24x7_probe"
        ):
            raise RuntimeError("probe_contract_invalid")
        return _emit("embedded_probe_resolved")

    if args.mode == "probe-missing":
        try:
            recovery._load_identity_probe()
        except recovery.RecoveryError as exc:
            if str(exc) == "live_probe_source_unavailable":
                return _emit("embedded_probe_missing_fail_closed")
        raise RuntimeError("missing_probe_not_rejected")

    if args.gateway_script is None or args.policy is None or args.interpreter is None:
        parser.error("gateway-validation requires gateway, policy and interpreter")
    gateway = _load(args.gateway_script, "_reqsys_fixed_command_gateway")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    command = [
        str(args.interpreter),
        str(args.recovery_script),
        "deploy-check",
        "--expected-sha",
        "0" * 40,
    ]
    gateway.validate_command(command, 2, policy)
    resolved = gateway.python_script_path(command, args.recovery_script.parent.parent)
    if resolved is None or resolved.resolve() != args.recovery_script.resolve():
        raise RuntimeError("gateway_python_script_resolution_invalid")
    return _emit("gateway_accepts_pinned_python")


if __name__ == "__main__":
    raise SystemExit(main())
