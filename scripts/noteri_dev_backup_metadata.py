#!/usr/bin/env python3
"""Inspect only backup metadata at the fixed, authorized Noteri location."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import urllib.request

def collect() -> dict:
    if socket.gethostname().casefold() != "noteri":
        raise RuntimeError("NOTERI_HOST_MISMATCH")
    if os.environ.get("GITHUB_REPOSITORY") != "ericson-j-santos/reqsys-v2-enterprise-real":
        raise RuntimeError("REPOSITORY_MISMATCH")
    root = Path(r"C:\Users\erics\AppData\Local\ReqSys\MigrationBackups\20261002-1912")
    files = []
    if root.is_dir() and not root.is_symlink():
        for folder in (root, *[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]):
            for file in folder.iterdir():
                if len(files) >= 120:
                    break
                if file.is_symlink():
                    continue
                if file.is_file():
                    files.append({"name": file.relative_to(root).as_posix(),
                                  "size": file.stat().st_size})
    manifests = []
    for filename in ("reqsys-dev-manifest.json", "encrypted-backup-evidence.json", "evidence.json", "restore-evidence.json"):
        path = root / filename
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536:
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                safe = {"name": filename, "top_level_fields": sorted(data) if isinstance(data, dict) else []}
                if isinstance(data, dict):
                    for key in ("sha256", "snapshot", "snapshot_id", "restic_snapshot", "restored_sha256"):
                        value = data.get(key)
                        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                            safe[key] = value
                    for key in ("table_count", "row_count", "rows", "bytes"):
                        value = data.get(key)
                        if isinstance(value, int) and not isinstance(value, bool):
                            safe[key] = value
                manifests.append(safe)
            except (OSError, ValueError):
                manifests.append({"name": filename, "parse_ok": False})
    executable = shutil.which("restic")
    candidates = [root / "restic.exe", root.parent / "tools" / "restic.exe",
                  Path(os.environ["LOCALAPPDATA"]) / "ReqSys" / "Tools" / "restic.exe"]
    if not executable:
        executable = next((str(p) for p in candidates if p.is_file() and not p.is_symlink()), None)
    restic = {"available": bool(executable)}
    if executable:
        restic["executable"] = executable
        try:
            result = subprocess.run([executable, "version"], capture_output=True, text=True, timeout=15)
            match = re.search(r"restic (\d+\.\d+\.\d+)", result.stdout)
            restic["version"] = match.group(1) if result.returncode == 0 and match else "unverified"
        except (OSError, subprocess.TimeoutExpired):
            restic["version"] = "unavailable"
    distribution = {"version": "0.18.0", "zip_sha256": None}
    try:
        url = "https://github.com/restic/restic/releases/download/v0.18.0/SHA256SUMS"
        with urllib.request.urlopen(url, timeout=20) as response:
            final = response.geturl()
            if not final.startswith("https://"):
                raise ValueError("checksum_transport_invalid")
            sums = response.read(16384).decode("ascii")
        match = re.search(r"^([0-9a-f]{64})\s+\*?restic_0\.18\.0_windows_amd64\.zip$", sums, re.M)
        if match:
            distribution["zip_sha256"] = match.group(1)
    except (OSError, ValueError):
        pass
    return {"schema_version": 1, "host": "Noteri", "source_sha": os.environ.get("GITHUB_SHA"),
            "correlation_id": os.environ.get("CORRELATION_ID"),
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "backup_directory_present": root.is_dir(), "relative_files": files,
            "manifest_metadata": manifests, "restic": restic, "restic_distribution": distribution,
            "password_values_read": False, "database_rows_read": False,
            "data_transferred": False, "phase": "backup_metadata_preflight"}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
