from __future__ import annotations

import argparse
import http.server
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
RDP_PORT = 3389
SERVE_PORT = 8767
REQUIRED_CAPS = {
    "host.inventory.files.v1",
    "host.orchestrator.refresh.v1",
    "host.github_runner.recover.v1",
}
CONFIRM = "BOOTSTRAP-DESKTOP-VIA-NATIVE-RDP"


class BootstrapError(RuntimeError):
    pass


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def saved_termsrv_credential() -> bool:
    completed = subprocess.run(
        ["cmdkey.exe", "/list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return False
    normalized = completed.stdout.casefold().replace(" ", "")
    markers = (
        "termsrv/desktop-pdqk954",
        "termsrv\\desktop-pdqk954",
    )
    return any(marker in normalized for marker in markers)


def worker_state() -> dict[str, Any]:
    request = urllib.request.Request(
        "http://DESKTOP-PDQK954:8787/v1/workers",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"orchestrator_unavailable:{type(exc).__name__}") from exc
    workers = payload.get("workers") if isinstance(payload, dict) else None
    if not isinstance(workers, list):
        raise BootstrapError("workers_invalid")
    matches = [
        item for item in workers
        if isinstance(item, dict)
        and str(item.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise BootstrapError("desktop_worker_not_unique")
    item = matches[0]
    caps = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
    safe = caps.get("safe_task_types") if isinstance(caps.get("safe_task_types"), list) else []
    return {
        "fresh": item.get("fresh") is True,
        "eligible": item.get("eligible") is True,
        "controller_version": str(item.get("controller_version") or ""),
        "safe_task_types": sorted(x for x in safe if isinstance(x, str)),
        "required_capabilities_present": REQUIRED_CAPS.issubset(set(safe)),
    }


class SingleFileHandler(http.server.BaseHTTPRequestHandler):
    bootstrap_path: Path

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path != "/Activate-Desktop-Stable-Bootstrap.cmd":
            self.send_response(404)
            self.end_headers()
            return
        raw = self.bootstrap_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def write_rdp(path: Path) -> None:
    bootstrap_url = f"http://{EXPECTED_SOURCE_HOST}:{SERVE_PORT}/Activate-Desktop-Stable-Bootstrap.cmd"
    remote_cmd = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
        f'\"$u=\'{bootstrap_url}\';'
        "$p=Join-Path $env:TEMP 'Activate-Desktop-Stable-Bootstrap.cmd';"
        "Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p -TimeoutSec 20;"
        "& $p\""
    )
    lines = [
        f"full address:s:{TARGET_HOST}",
        "screen mode id:i:1",
        "desktopwidth:i:1024",
        "desktopheight:i:768",
        "prompt for credentials:i:0",
        "authentication level:i:2",
        "enablecredsspsupport:i:1",
        "administrative session:i:1",
        "redirectclipboard:i:0",
        "redirectprinters:i:0",
        "redirectcomports:i:0",
        "redirectsmartcards:i:0",
        "drivestoredirect:s:",
        f"alternate shell:s:{remote_cmd}",
        "shell working directory:s:C:\\Windows\\System32",
    ]
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def execute(bootstrap_path: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    if os.name != "nt" or socket.gethostname().casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise BootstrapError("source_host_not_authorized")
    if not bootstrap_path.is_file():
        raise BootstrapError("bootstrap_artifact_missing")
    if not tcp_open(TARGET_HOST, RDP_PORT):
        raise BootstrapError("rdp_tcp_3389_closed")
    mstsc = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "mstsc.exe"
    if not mstsc.is_file():
        raise BootstrapError("mstsc_missing")
    if not saved_termsrv_credential():
        raise BootstrapError("saved_termsrv_credential_missing")

    before = worker_state()
    if before["required_capabilities_present"]:
        return {
            "ok": True,
            "replayed": True,
            "route": "native_rdp_saved_credential",
            "before": before,
            "after": before,
            "rdp_port_open": True,
            "saved_credential_present": True,
            "credential_value_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }

    handler = type("BootstrapHandler", (SingleFileHandler,), {})
    handler.bootstrap_path = bootstrap_path.resolve()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", SERVE_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rdp_path: Path | None = None
    process: subprocess.Popen[Any] | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rdp", delete=False, encoding="utf-8"
        ) as handle:
            rdp_path = Path(handle.name)
        write_rdp(rdp_path)
        process = subprocess.Popen(
            [str(mstsc), str(rdp_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + timeout_seconds
        after = before
        while time.monotonic() < deadline:
            time.sleep(3)
            try:
                after = worker_state()
            except BootstrapError:
                continue
            if (
                after.get("fresh") is True
                and after.get("eligible") is True
                and after.get("required_capabilities_present") is True
            ):
                return {
                    "ok": True,
                    "replayed": False,
                    "route": "native_rdp_saved_credential",
                    "before": before,
                    "after": after,
                    "rdp_port_open": True,
                    "saved_credential_present": True,
                    "credential_value_read": False,
                    "mstsc_started": True,
                    "production_touched": False,
                    "reboot_performed": False,
                }
        raise BootstrapError("bootstrap_capability_readback_timeout")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if process is not None and process.poll() is None:
            process.terminate()
        if rdp_path is not None:
            rdp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--bootstrap-path", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        return 2
    try:
        payload = execute(args.bootstrap_path)
        code = 0
    except Exception as exc:
        payload = {
            "ok": False,
            "route": "native_rdp_saved_credential",
            "error": "native_rdp_bootstrap_failed",\n            "error_type": type(exc).__name__,
            "rdp_port_open": tcp_open(TARGET_HOST, RDP_PORT),
            "saved_credential_present": saved_termsrv_credential() if os.name == "nt" else False,
            "credential_value_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        code = 3
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
