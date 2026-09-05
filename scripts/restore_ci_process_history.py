#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WORKFLOW_FILE = "ci-lead-time-analytics.yml"
OUTPUT_HISTORY_PATH = "audit/history/ci-process-improvement-history.jsonl"
ARCHIVE_HISTORY_MEMBERS = (
    "history/ci-process-improvement-history.jsonl",
    OUTPUT_HISTORY_PATH,
)


def _request_json(url: str, token: str) -> dict:
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urlopen(req, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _request_bytes(url: str, token: str) -> bytes:
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urlopen(req, timeout=30) as response:  # noqa: S310
        return response.read()


def restore(repo: str, token: str, output: Path, current_run_id: str = "") -> int:
    base = f"https://api.github.com/repos/{repo}"
    runs = _request_json(f"{base}/actions/workflows/{WORKFLOW_FILE}/runs?branch=main&status=success&per_page=20", token)
    for run in runs.get("workflow_runs", []):
        run_id = str(run.get("id", ""))
        if not run_id or run_id == current_run_id:
            continue
        artifacts = _request_json(f"{base}/actions/runs/{run_id}/artifacts?per_page=100", token)
        expected_name = f"ci-lead-time-analytics-{run_id}"
        for artifact in artifacts.get("artifacts", []):
            if artifact.get("expired") or artifact.get("name") != expected_name:
                continue
            archive = _request_bytes(f"{base}/actions/artifacts/{artifact['id']}/zip", token)
            with zipfile.ZipFile(io.BytesIO(archive)) as zf:
                archive_member = next((member for member in ARCHIVE_HISTORY_MEMBERS if member in zf.namelist()), None)
                if archive_member is None:
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(zf.read(archive_member))
                print(json.dumps({"restored": True, "source_run_id": run_id, "artifact_id": artifact["id"], "archive_member": archive_member, "path": str(output)}))
                return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"restored": False, "reason": "no_prior_main_history_artifact", "path": str(output)}))
    return 0


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    output = Path(os.environ.get("CI_PROCESS_HISTORY_PATH", OUTPUT_HISTORY_PATH))
    if not repo or not token:
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2
    try:
        return restore(repo, token, output, os.environ.get("GITHUB_RUN_ID", ""))
    except (HTTPError, URLError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f"history restore warning: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
