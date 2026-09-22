#!/usr/bin/env python3
"""Consolidate Cofre runtime evidence without handling secret values."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(root: Path, name: str):
    path = root / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def consolidate(
    *,
    root: Path,
    base_url: str,
    workflow_sha: str,
    run_id: str,
    run_attempt: str,
    correlation_id: str,
) -> dict:
    before = load_json(root, "before-restart.json")
    after = load_json(root, "after-restart.json")
    restart = load_json(root, "runtime-restart.json")
    verified = load_json(root, "runtime-restart-verified.json")
    items = (before, after, restart, verified)
    ok = all(item is not None and item.get("ok") is True for item in items)
    ok = ok and bool(verified and verified.get("boot_id_changed") is True)
    return {
        "schema_version": "3.0.0",
        "contract": "reqsys-cofre-runtime-evidence-summary",
        "ok": ok,
        "environment": "dev",
        "runtime_target": "pc24x7",
        "control_plane": "authenticated_remote_self_restart",
        "base_url": base_url.rstrip("/"),
        "workflow_sha": workflow_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "correlation_id": correlation_id,
        "restart_runtime": True,
        "boot_id_changed": bool(verified and verified.get("boot_id_changed")),
        "transient_state_encrypted": True,
        "production_touched": False,
        "sensitive_values_exposed": False,
        "phases": {
            "before-restart": before,
            "after-restart": after,
        },
        "runtime_control": restart,
        "runtime_restart_verification": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    payload = consolidate(
        root=args.artifact_dir,
        base_url=args.base_url,
        workflow_sha=args.workflow_sha,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        correlation_id=args.correlation_id,
    )
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    (args.artifact_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": payload["ok"], "summary": str(args.artifact_dir / "summary.json")}))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
