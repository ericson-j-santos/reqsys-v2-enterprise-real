#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
WORKFLOW = "parallel-development-acceleration.yml"


class DispatchError(RuntimeError):
    pass


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise DispatchError(f"tool_missing:{name}")


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise DispatchError(f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:500]}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()

    gh = _tool("gh")
    _run([gh, "auth", "status", "--hostname", "github.com"], timeout=30)
    started = datetime.now(timezone.utc).isoformat()
    _run(
        [
            gh, "workflow", "run", WORKFLOW,
            "--repo", REPOSITORY,
            "--ref", args.branch,
        ],
        timeout=60,
    )

    run = None
    for _ in range(120):
        rows = json.loads(
            _run(
                [
                    gh, "run", "list",
                    "--repo", REPOSITORY,
                    "--workflow", WORKFLOW,
                    "--branch", args.branch,
                    "--event", "workflow_dispatch",
                    "--limit", "20",
                    "--json", "databaseId,headSha,status,conclusion,createdAt,url",
                ],
                timeout=60,
            ).stdout or "[]"
        )
        run = next(
            (
                item for item in rows
                if item.get("headSha") == args.expected_head
                and str(item.get("createdAt") or "") >= started
            ),
            None,
        )
        if run and run.get("status") == "completed":
            break
        time.sleep(5)

    if not run:
        raise DispatchError("workflow_run_not_found")
    if run.get("headSha") != args.expected_head:
        raise DispatchError("workflow_sha_mismatch")
    print(json.dumps(run, ensure_ascii=False, sort_keys=True))
    return 0 if run.get("conclusion") == "success" else 4


if __name__ == "__main__":
    raise SystemExit(main())
