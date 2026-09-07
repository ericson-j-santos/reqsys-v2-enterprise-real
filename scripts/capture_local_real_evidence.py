#!/usr/bin/env python3
"""Start local backend/frontend and capture browser evidence for real acceptance validation.

This script is intentionally small and deterministic: it starts the backend on a local
port, waits for health checks, starts the frontend dev server, waits for page availability,
then uses Playwright to open the app and take a screenshot. The resulting JSON artifact is
written under artifacts/real-evidence-local/ so downstream acceptance jobs can rely on it.

Usage:
    python scripts/capture_local_real_evidence.py
    python scripts/capture_local_real_evidence.py --keep-running
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
ARTIFACT_DIR = ROOT / "artifacts" / "real-evidence-local"


def _find_command(*candidates: str) -> str:
    for name in candidates:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    for name in candidates:
        windows_name = f"{name}.cmd" if os.name == "nt" and not name.endswith(".exe") and not name.endswith(".cmd") else name
        resolved = shutil.which(windows_name)
        if resolved:
            return resolved
    raise FileNotFoundError(f"Command not found among: {candidates}")


def _find_python() -> str:
    candidates: list[Path] = [
        BACKEND_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python"),
        Path(shutil.which("python") or ""),
        Path(shutil.which("python3") or ""),
    ]
    for path in candidates:
        if path and path.exists():
            return str(path)
    raise FileNotFoundError("Python interpreter not found for backend runtime")


def _wait_for_url(url: str, timeout_seconds: int = 90, request_timeout: int = 5) -> tuple[int, Any]:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            request = Request(url, headers={"User-Agent": "reqsys-real-evidence/1.0", "Accept": "application/json, text/html"})
            with urlopen(request, timeout=request_timeout) as response:
                raw = response.read(65536)
                return response.status, raw
        except (URLError, HTTPError, TimeoutError, OSError) as exc:  # pragma: no cover - runtime guard
            last_error = exc
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _is_endpoint_ready(url: str, timeout_seconds: int = 10) -> bool:
    try:
        _wait_for_url(url, timeout_seconds=timeout_seconds)
        return True
    except Exception:
        return False


def _terminate_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
    except OSError:
        return
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            process.send_signal(signal.SIGKILL)
        process.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture local real-evidence smoke for ReqSys")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--keep-running", action="store_true", help="Keep both services alive after evidence capture")
    args = parser.parse_args()

    python_cmd = _find_python()
    if not (BACKEND_DIR / "app").exists():
        raise FileNotFoundError(f"Backend application directory not found at {BACKEND_DIR / 'app'}")
    if not (FRONTEND_DIR / "package.json").exists():
        raise FileNotFoundError(f"Frontend package.json not found at {FRONTEND_DIR}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = ARTIFACT_DIR / "local-frontend-evidence.png"
    summary_path = ARTIFACT_DIR / "local-evidence-summary.json"

    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND_DIR) + (os.pathsep + backend_env["PYTHONPATH"] if backend_env.get("PYTHONPATH") else "")
    backend_url = f"http://127.0.0.1:{args.backend_port}/health"
    backend_proc = None
    if not _is_endpoint_ready(backend_url, timeout_seconds=3):
        backend_proc = subprocess.Popen(
            [python_cmd, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.backend_port)],
            cwd=str(BACKEND_DIR),
            env=backend_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    frontend_url = f"http://127.0.0.1:{args.frontend_port}/login"
    frontend_proc = None
    if not _is_endpoint_ready(frontend_url, timeout_seconds=3):
        frontend_env = os.environ.copy()
        frontend_env["VITE_API_URL"] = "/api"
        npm_cmd = _find_command("npm", "npm.cmd")
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.frontend_port)],
            cwd=str(FRONTEND_DIR),
            env=frontend_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    try:
        backend_status, backend_raw = _wait_for_url(backend_url, timeout_seconds=args.timeout_seconds)
        frontend_status, frontend_raw = _wait_for_url(frontend_url, timeout_seconds=args.timeout_seconds)

        browser_script = r'''
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const target = process.argv[1];
  const savePath = process.argv[2];
  await page.goto(target, { waitUntil: 'networkidle', timeout: 45000 });
  const title = await page.title();
  const url = page.url();
  await page.screenshot({ path: savePath, fullPage: true });
  console.log(JSON.stringify({ title, url }));
  await browser.close();
})();
'''

        node_cmd = _find_command("node", "node.exe")
        browser_result = subprocess.run(
            [node_cmd, "-e", browser_script, f"http://127.0.0.1:{args.frontend_port}/", str(screenshot_path)],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        browser_data = json.loads(browser_result.stdout.strip().splitlines()[-1])

        summary = {
            "schema_version": "1.0.0",
            "kind": "local-real-evidence",
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backend": {
                "url": f"http://127.0.0.1:{args.backend_port}",
                "health_url": f"http://127.0.0.1:{args.backend_port}/health",
                "status_code": backend_status,
                "response_preview": backend_raw[:400].decode("utf-8", errors="ignore"),
            },
            "frontend": {
                "url": f"http://127.0.0.1:{args.frontend_port}/",
                "login_url": f"http://127.0.0.1:{args.frontend_port}/login",
                "status_code": frontend_status,
                "response_preview": frontend_raw[:400].decode("utf-8", errors="ignore"),
                "page_title": browser_data.get("title"),
                "page_url": browser_data.get("url"),
                "screenshot_path": str(screenshot_path.relative_to(ROOT)),
            },
            "evidence_status": "captured",
        }

        _write_json(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    finally:
        if not args.keep_running:
            _terminate_process(backend_proc)
            _terminate_process(frontend_proc)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
