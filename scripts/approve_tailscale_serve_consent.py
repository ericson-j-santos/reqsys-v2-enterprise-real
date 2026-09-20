#!/usr/bin/env python3
"""Automação fail-closed do consentimento Tailscale Serve no Windows."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any

CONSENT_RE = re.compile(r"https://login\.tailscale\.com/f/serve\?[^\s]+")
APPROVE_LABELS = {
    "Enable Tailscale Serve",
    "Enable Serve",
    "Enable HTTPS",
    "Ativar Tailscale Serve",
    "Ativar Serve",
    "Ativar HTTPS",
}
AUTH_MARKERS = ("sign in", "log in", "github", "entrar", "login")


class ConsentError(RuntimeError):
    pass


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def find_tailscale() -> Path:
    found = shutil.which("tailscale")
    if found:
        return Path(found)
    candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"
    if candidate.is_file():
        return candidate
    raise ConsentError("tailscale_cli_not_found")


def extract_consent_url(output: str) -> str:
    match = CONSENT_RE.search(output)
    if not match:
        raise ConsentError("serve_consent_url_not_found")
    return match.group(0)


def request_consent_url(binary: Path, https_port: int) -> str:
    proc = subprocess.Popen(
        [
            str(binary),
            "serve",
            "--bg",
            "--yes",
            f"--https={https_port}",
            "http://127.0.0.1:11434",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,
    )
    try:
        output, _ = proc.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        output, _ = proc.communicate(timeout=5)
    return extract_consent_url(output or "")


def browser_snapshot() -> dict[str, Any]:
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise ConsentError("pywinauto_not_available") from exc
    windows = []
    for window in Desktop(backend="uia").windows():
        try:
            title = (window.window_text() or "").strip()
            buttons = []
            texts = []
            for control in window.descendants():
                try:
                    label = (control.window_text() or "").strip()
                    ctype = str(control.element_info.control_type or "")
                except Exception:
                    continue
                if not label:
                    continue
                if ctype == "Button" and label not in buttons:
                    buttons.append(label)
                if ctype in {"Text", "Document"} and label not in texts:
                    texts.append(label)
            combined = " ".join([title, *buttons, *texts]).casefold()
            if any(marker in combined for marker in ("tailscale", "serve", "sign in", "log in", "github", "entrar")):
                windows.append({"title": title, "buttons": buttons[:40], "texts": texts[:40]})
        except Exception:
            continue
    return {"windows": windows}


def approval_target(snapshot: dict[str, Any]) -> tuple[str | None, bool]:
    auth_required = False
    for window in snapshot.get("windows", []):
        for label in window.get("buttons", []):
            if label in APPROVE_LABELS:
                return label, False
            if any(marker in label.casefold() for marker in AUTH_MARKERS):
                auth_required = True
        for label in window.get("texts", []):
            if any(marker in label.casefold() for marker in AUTH_MARKERS):
                auth_required = True
    return None, auth_required


def control_diagnostics(labels: set[str]) -> list[dict[str, Any]]:
    from pywinauto import Desktop

    rows: list[dict[str, Any]] = []
    for window in Desktop(backend="uia").windows():
        try:
            for control in window.descendants():
                try:
                    label = (control.window_text() or "").strip()
                    ctype = str(control.element_info.control_type or "")
                    if label not in labels and ctype != "TabItem":
                        continue
                    rect = control.rectangle()
                    rows.append(
                        {
                            "window": (window.window_text() or "").strip(),
                            "label": label,
                            "control_type": ctype,
                            "automation_id": str(control.element_info.automation_id or ""),
                            "class_name": str(control.element_info.class_name or ""),
                            "visible": bool(control.is_visible()),
                            "enabled": bool(control.is_enabled()),
                            "rectangle": [rect.left, rect.top, rect.right, rect.bottom],
                        }
                    )
                except Exception as exc:
                    rows.append({"error": type(exc).__name__})
        except Exception as exc:
            rows.append({"window_error": type(exc).__name__})
    return rows


def click_exact(label: str) -> tuple[bool, list[dict[str, Any]]]:
    from pywinauto import Desktop

    attempts: list[dict[str, Any]] = []
    for window in Desktop(backend="uia").windows():
        try:
            for control in window.descendants(control_type="Button"):
                if (control.window_text() or "").strip() != label:
                    continue
                try:
                    rect = control.rectangle()
                    row = {
                        "window": (window.window_text() or "").strip(),
                        "label": label,
                        "visible": bool(control.is_visible()),
                        "enabled": bool(control.is_enabled()),
                        "rectangle": [rect.left, rect.top, rect.right, rect.bottom],
                    }
                    try:
                        window.set_focus()
                    except Exception as exc:
                        row["focus_error"] = type(exc).__name__
                    try:
                        control.invoke()
                        row["method"] = "invoke"
                        attempts.append(row)
                        return True, attempts
                    except Exception as exc:
                        row["invoke_error"] = type(exc).__name__
                    try:
                        control.click_input()
                        row["method"] = "click_input"
                        attempts.append(row)
                        return True, attempts
                    except Exception as exc:
                        row["click_error"] = type(exc).__name__
                    attempts.append(row)
                except Exception as exc:
                    attempts.append({"window": (window.window_text() or "").strip(), "label": label, "error": type(exc).__name__})
        except Exception as exc:
            attempts.append({"window_error": type(exc).__name__})
    return False, attempts


def run(mode: str, https_port: int, wait_seconds: int) -> dict[str, Any]:
    if mode in {"authorize-github-oauth", "confirm-github-mobile"}:
        opened = False
    else:
        url = request_consent_url(find_tailscale(), https_port)
        opened = bool(webbrowser.open(url, new=2))
    time.sleep(wait_seconds)
    snapshot = browser_snapshot()
    target, auth_required = approval_target(snapshot)
    base = {
        "ok": True,
        "browser_opened": opened,
        "approval_target": target,
        "auth_required": auth_required,
        "snapshot": snapshot,
    }
    if mode == "diagnose":
        return {
            **base,
            "controls": control_diagnostics({"Authorize tailscale", "Grant", "Cancel", "Sign in with GitHub", *APPROVE_LABELS}),
        }
    if mode == "probe":
        return base
    if mode == "confirm-github-mobile":
        mobile_label = "Use GitHub Mobile"
        present = any(
            mobile_label in window.get("buttons", []) for window in snapshot.get("windows", [])
        )
        if not present:
            return {**base, "ok": False, "result": "github_mobile_control_not_found"}
        clicked, attempts = click_exact(mobile_label)
        time.sleep(4)
        return {
            **base,
            "ok": clicked,
            "result": "github_mobile_challenge_started" if clicked else "github_mobile_click_failed",
            "click_attempts": attempts,
            "after": browser_snapshot(),
        }
    if mode == "authorize-github-oauth":
        oauth_label = "Authorize tailscale"
        grant_label = "Grant"
        diagnostics = control_diagnostics({oauth_label, grant_label})
        oauth_present = any(row.get("label") == oauth_label for row in diagnostics)
        oauth_enabled = any(
            row.get("label") == oauth_label and row.get("enabled") is True for row in diagnostics
        )
        grant_enabled = any(
            row.get("label") == grant_label and row.get("enabled") is True for row in diagnostics
        )
        grant_attempts: list[dict[str, Any]] = []
        if not oauth_present:
            return {**base, "ok": False, "result": "github_oauth_control_not_found", "controls": diagnostics}
        if not oauth_enabled and grant_enabled:
            grant_clicked, grant_attempts = click_exact(grant_label)
            if not grant_clicked:
                return {
                    **base,
                    "ok": False,
                    "result": "github_org_grant_click_failed",
                    "grant_attempts": grant_attempts,
                    "controls": diagnostics,
                }
            time.sleep(5)
            diagnostics = control_diagnostics({oauth_label, grant_label})
            oauth_enabled = any(
                row.get("label") == oauth_label and row.get("enabled") is True for row in diagnostics
            )
        if not oauth_enabled:
            return {
                **base,
                "ok": False,
                "result": "github_oauth_control_disabled",
                "grant_attempts": grant_attempts,
                "controls": diagnostics,
            }
        clicked, attempts = click_exact(oauth_label)
        time.sleep(6)
        return {
            **base,
            "ok": clicked,
            "result": "github_oauth_authorized" if clicked else "github_oauth_click_failed",
            "grant_attempts": grant_attempts,
            "click_attempts": attempts,
            "after": browser_snapshot(),
        }
    if mode == "login-github":
        if target:
            return {**base, "result": "approval_already_available"}
        github_label = "Sign in with GitHub"
        github_present = any(
            github_label in window.get("buttons", []) for window in snapshot.get("windows", [])
        )
        if not github_present:
            return {**base, "ok": False, "result": "github_signin_control_not_found"}
        clicked, attempts = click_exact(github_label)
        time.sleep(5)
        return {
            **base,
            "ok": clicked,
            "result": "github_signin_clicked" if clicked else "github_signin_click_failed",
            "click_attempts": attempts,
            "after": browser_snapshot(),
        }
    if auth_required and not target:
        return {**base, "ok": False, "result": "interactive_auth_required"}
    if not target:
        return {**base, "ok": False, "result": "approval_control_not_found"}
    clicked, attempts = click_exact(target)
    time.sleep(3)
    return {
        **base,
        "ok": clicked,
        "result": "approval_clicked" if clicked else "approval_click_failed",
        "click_attempts": attempts,
        "after": browser_snapshot(),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("probe", "diagnose", "login-github", "authorize-github-oauth", "confirm-github-mobile", "approve"))
    p.add_argument("--https-port", type=int, default=11443)
    p.add_argument("--wait-seconds", type=int, default=6)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        payload = run(args.mode, args.https_port, args.wait_seconds)
        emit(payload)
        return 0 if payload.get("ok") else 2
    except (ConsentError, OSError, subprocess.SubprocessError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
